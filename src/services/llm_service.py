"""LLM integration service for generating storylets."""

import logging
import os
import json
import re
import time
from copy import deepcopy
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator, model_validator

from . import runtime_metrics
from .llm_client import (
    get_llm_client,
    get_narrator_model,
    get_referee_model,
    get_trace_id,
    is_ai_disabled,
    run_inference_thread,
)
from .llm_json import (
    LLMJsonError,
    extract_json_array,
    extract_json_object,
    extract_json_value,
    validate_with_model,
)
from ..config import settings
from . import prompt_library

logger = logging.getLogger(__name__)

_FALLBACK_STORYLETS: List[Dict[str, Any]] = [
    {
        "title": "Quantum Whispers",
        "text_template": "\U0001f30c {name} senses subtle vibrations in the cosmic frequencies. Resonance: {resonance}.",
        "requires": {"resonance": {"lte": 1}},
        "choices": [
            {"label": "Attune deeper", "set": {"resonance": {"inc": 1}}},
            {"label": "Stabilize flow", "set": {"resonance": {"dec": 1}}},
        ],
        "weight": 1.2,
    },
    {
        "title": "Stellar Resonance",
        "text_template": "\u2728 Crystalline formations pulse with cosmic energy, singing in harmonic frequencies.",
        "requires": {"has_crystal": True},
        "choices": [
            {"label": "Attune to frequencies", "set": {"energy": {"inc": 1}}},
            {"label": "Preserve the harmony", "set": {}},
        ],
        "weight": 1.0,
    },
]
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_RETRYABLE_ERROR_NAMES = {"APITimeoutError", "APIConnectionError", "RateLimitError"}
_RUNTIME_ADAPT_EVENT_LIMIT = 3
_RUNTIME_SYNTHESIS_MAX_CHOICES = 3
_PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z0-9_.-]+)\}")


def _coerce_non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(round(value)))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        try:
            return max(0, int(round(float(stripped))))
        except ValueError:
            return 0
    return 0


def _extract_token_usage(response: Any) -> Dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        completion_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        total_tokens = usage.get("total_tokens")
    else:
        prompt_tokens = getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", None))
        completion_tokens = getattr(
            usage,
            "completion_tokens",
            getattr(usage, "output_tokens", None),
        )
        total_tokens = getattr(usage, "total_tokens", None)

    input_tokens = _coerce_non_negative_int(prompt_tokens)
    output_tokens = _coerce_non_negative_int(completion_tokens)
    total = _coerce_non_negative_int(total_tokens) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
    }


def _log_llm_call_metrics(
    *,
    operation: str,
    model: str,
    duration_ms: float,
    status: str,
    attempt: int,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    error_type: Optional[str] = None,
) -> None:
    safe_attempt = _coerce_non_negative_int(attempt) or 1
    safe_input_tokens = _coerce_non_negative_int(input_tokens)
    safe_output_tokens = _coerce_non_negative_int(output_tokens)
    safe_total_tokens = _coerce_non_negative_int(total_tokens)

    payload: Dict[str, Any] = {
        "event": "llm_service_call_metrics",
        "component": "llm_service",
        "operation": operation,
        "trace_id": get_trace_id(),
        "model": model,
        "status": status,
        "duration_ms": round(max(0.0, float(duration_ms)), 3),
        "attempt": int(safe_attempt),
        "input_tokens": int(safe_input_tokens),
        "output_tokens": int(safe_output_tokens),
        "total_tokens": int(safe_total_tokens),
    }
    if error_type:
        payload["error_type"] = str(error_type)

    logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str))
    runtime_metrics.record_llm_call(
        component="llm_service",
        operation=operation,
        model=model,
        duration_ms=duration_ms,
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        trace_id=get_trace_id(),
    )


def _fallback_storylets_for_n(n: int) -> List[Dict[str, Any]]:
    """Return deterministic local fallback storylets sized for the request."""
    return _FALLBACK_STORYLETS[: max(1, int(n or 1))]


class _StoryletPayloadModel(BaseModel):
    title: str
    text_template: str = ""
    text: str = ""

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        title = str(value or "").strip()
        if not title:
            raise ValueError("missing required 'title'")
        return title

    @model_validator(mode="after")
    def _validate_text_fields(self) -> "_StoryletPayloadModel":
        text_template = str(self.text_template or "").strip()
        text = str(self.text or "").strip()
        if not text_template and not text:
            raise ValueError("missing required 'text_template' or 'text'")
        self.text_template = text_template
        self.text = text
        return self


def _validate_storylet_payload(items: Any) -> List[Dict[str, Any]]:
    """Validate and normalize a list of generated storylet-like objects."""
    if not isinstance(items, list):
        raise ValueError("Storylet payload must be a JSON array")

    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Storylet at index {idx} is not an object")
        validate_with_model(item, _StoryletPayloadModel)
        normalized.append(item)

    return normalized


def _extract_json_storylet_list(text: str) -> List[Dict[str, Any]]:
    """Parse model output into a validated list of storylet-like dicts."""
    value = extract_json_array(text, wrapper_keys=("storylets",))
    return _validate_storylet_payload(value)


def _extract_json_object(text: str) -> Dict[str, Any]:
    """Parse model output into a JSON object."""
    return extract_json_object(text)


def _normalize_storylet_choices(raw_choices: Any) -> List[Dict[str, Any]]:
    """Normalize loose choice payloads to canonical {label, set} entries."""
    normalized: List[Dict[str, Any]] = []
    if not isinstance(raw_choices, list):
        return normalized
    for raw_choice in raw_choices:
        if not isinstance(raw_choice, dict):
            continue
        label = str(raw_choice.get("label") or raw_choice.get("text") or "").strip()
        if not label:
            continue
        set_payload = raw_choice.get("set")
        if not isinstance(set_payload, dict):
            set_payload = raw_choice.get("set_vars")
        if not isinstance(set_payload, dict):
            set_payload = {}
        normalized.append({"label": label, "set": set_payload})
    return normalized


def _reduce_storylet_contracts(
    raw_contracts: Any,
    *,
    count: int,
    theme: str,
) -> List[Dict[str, Any]]:
    """Reducer step: normalize referee contracts into bounded storylet specs."""
    if not isinstance(raw_contracts, list):
        raise ValueError("referee payload must include a storylet contract array")

    reduced: List[Dict[str, Any]] = []
    seen_titles: set[str] = set()
    for idx, raw_item in enumerate(raw_contracts):
        if len(reduced) >= count:
            break
        if not isinstance(raw_item, dict):
            continue

        base_title = str(raw_item.get("title") or f"{theme.title()} Thread {idx + 1}").strip()
        if not base_title:
            base_title = f"{theme.title()} Thread {idx + 1}"
        title = base_title
        suffix = 2
        while title in seen_titles:
            title = f"{base_title} ({suffix})"
            suffix += 1
        seen_titles.add(title)

        premise = str(raw_item.get("premise") or raw_item.get("text") or raw_item.get("text_template") or "A new thread opens in the world.").strip()
        if not premise:
            premise = "A new thread opens in the world."

        requires = raw_item.get("requires")
        if not isinstance(requires, dict):
            requires = {}

        choices = _normalize_storylet_choices(raw_item.get("choices"))
        while len(choices) < 2:
            if len(choices) == 0:
                choices.append({"label": "Press forward", "set": {"momentum": {"inc": 1}}})
            else:
                choices.append({"label": "Pause and assess", "set": {"awareness": {"inc": 1}}})
        choices = choices[:_RUNTIME_SYNTHESIS_MAX_CHOICES]

        try:
            weight = float(raw_item.get("weight", 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        weight = max(0.2, min(3.0, weight))

        reduced.append(
            {
                "title": title,
                "premise": premise,
                "requires": requires,
                "choices": choices,
                "weight": round(weight, 3),
            }
        )

    if not reduced:
        raise ValueError("referee produced zero usable storylet contracts")

    return reduced


def _llm_json_error_category(exc: Exception) -> str:
    if isinstance(exc, LLMJsonError):
        return exc.error_category
    return "unknown_llm_json_error"


def _is_retryable_llm_error(exc: Exception) -> bool:
    """Return True when an LLM exception should be retried."""
    if isinstance(exc, TimeoutError):
        return True

    if exc.__class__.__name__ in _RETRYABLE_ERROR_NAMES:
        return True

    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int) and status_code in _RETRYABLE_STATUS_CODES:
        return True

    message = str(exc).lower()
    if "timed out" in message or "timeout" in message:
        return True
    if "rate limit" in message or "429" in message:
        return True

    return False


def _chat_completion_with_retry(
    client: Any,
    *,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: int,
    response_format: Optional[Dict[str, str]] = None,
    metric_operation: str = "unknown",
) -> Any:
    """Call chat completions with timeout/retry for transient failures."""
    max_retries = max(0, int(settings.llm_retries))
    backoff_seconds = 1.0

    for attempt in range(max_retries + 1):
        started = time.perf_counter()
        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": timeout,
                "frequency_penalty": float(settings.llm_frequency_penalty),
                "presence_penalty": float(settings.llm_presence_penalty),
            }
            if response_format:
                kwargs["response_format"] = response_format
            response = client.chat.completions.create(**kwargs)
            usage = _extract_token_usage(response)
            _log_llm_call_metrics(
                operation=metric_operation,
                model=model,
                duration_ms=(time.perf_counter() - started) * 1000.0,
                status="ok",
                attempt=attempt + 1,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                total_tokens=usage["total_tokens"],
            )
            return response
        except Exception as exc:
            _log_llm_call_metrics(
                operation=metric_operation,
                model=model,
                duration_ms=(time.perf_counter() - started) * 1000.0,
                status="error",
                attempt=attempt + 1,
                error_type=exc.__class__.__name__,
            )
            is_last_attempt = attempt >= max_retries
            if is_last_attempt or not _is_retryable_llm_error(exc):
                raise

            logger.warning(
                "Transient LLM error (attempt %d/%d): %s",
                attempt + 1,
                max_retries + 1,
                exc,
            )
            time.sleep(backoff_seconds)
            backoff_seconds *= 2.0


def _safe_render_template(template: str, variables: Dict[str, Any]) -> str:
    """Render text with graceful fallback for missing template keys."""

    class _SafeDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    return str(template or "").format_map(_SafeDict(variables or {}))


def _fill_unresolved_placeholders(text: str, context: Dict[str, Any]) -> str:
    """Resolve remaining placeholders from broader context when possible."""
    variables = context.get("variables", {})
    environment = context.get("environment", {})
    merged: Dict[str, Any] = {}
    if isinstance(environment, dict):
        merged.update(environment)
    if isinstance(variables, dict):
        merged.update(variables)

    def _replacement(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in merged:
            return str(merged[key])
        return key.replace("_", " ")

    return _PLACEHOLDER_PATTERN.sub(_replacement, str(text or ""))


def _normalize_adaptation_choices(raw_choices: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_choices, list):
        return out
    for choice in raw_choices:
        if not isinstance(choice, dict):
            continue
        out.append(
            {
                "label": str(choice.get("label") or choice.get("text") or "Continue"),
                "set": choice.get("set") or choice.get("set_vars") or {},
            }
        )
    return out


def _normalize_recent_motifs(raw: Any, *, limit: int = 40) -> List[str]:
    if not isinstance(raw, list):
        return []
    bounded = max(1, int(limit))
    out: List[str] = []
    seen: set[str] = set()
    for item in raw:
        motif = str(item or "").strip().lower()
        if not motif:
            continue
        if motif in seen:
            continue
        seen.add(motif)
        out.append(motif)
    return out[-bounded:]


def _normalize_sensory_palette(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for key, value in raw.items():
        label = str(key or "").strip().lower()
        if not label:
            continue
        text = str(value or "").strip()
        if not text:
            continue
        out[label] = text
    return out


def _run_motif_referee_audit(
    *,
    client: Any,
    draft_text: str,
    scene_card_now: Dict[str, Any],
    motifs_recent: List[str],
    sensory_palette: Dict[str, str],
    recent_events: List[str],
    operation: str,
) -> Dict[str, Any]:
    response = _chat_completion_with_retry(
        client,
        metric_operation=operation,
        model=get_referee_model(),
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": prompt_library.build_motif_auditor_system_prompt(),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "draft_text": draft_text,
                        "scene_card_now": scene_card_now,
                        "motifs_recent": motifs_recent,
                        "sensory_palette": sensory_palette,
                        "recent_events": recent_events[:5],
                        "output_contract": {
                            "decision": "ok|revise",
                            "overused_motifs": ["string"],
                            "replacement_anchors": ["string"],
                            "rationale": "string",
                        },
                    },
                    default=str,
                ),
            },
        ],
        temperature=max(0.0, min(1.0, float(settings.llm_referee_temperature))),
        max_tokens=min(280, int(settings.llm_max_tokens)),
        timeout=max(2, int(settings.llm_timeout_seconds)),
    )
    payload = _extract_json_object(response.choices[0].message.content or "{}")
    decision = str(payload.get("decision", "ok")).strip().lower()
    if decision not in {"ok", "revise"}:
        decision = "ok"
    return {
        "decision": decision,
        "overused_motifs": [str(item).strip().lower() for item in payload.get("overused_motifs", []) if str(item).strip()][:10],
        "replacement_anchors": [str(item).strip() for item in payload.get("replacement_anchors", []) if str(item).strip()][:6],
        "rationale": str(payload.get("rationale", "")).strip(),
    }


def _rewrite_text_with_motif_guidance(
    *,
    client: Any,
    draft_text: str,
    scene_card_now: Dict[str, Any],
    sensory_palette: Dict[str, str],
    overused_motifs: List[str],
    replacement_anchors: List[str],
    operation: str,
) -> str:
    response = _chat_completion_with_retry(
        client,
        metric_operation=operation,
        model=get_narrator_model(),
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": prompt_library.build_motif_revision_system_prompt(),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "draft_text": draft_text,
                        "scene_card_now": scene_card_now,
                        "sensory_palette": sensory_palette,
                        "overused_motifs": overused_motifs,
                        "replacement_anchors": replacement_anchors,
                    },
                    default=str,
                ),
            },
        ],
        temperature=max(0.0, min(1.2, float(settings.llm_narrator_temperature))),
        max_tokens=min(480, int(settings.llm_max_tokens)),
        timeout=max(2, int(settings.llm_timeout_seconds)),
    )
    payload = _extract_json_object(response.choices[0].message.content or "{}")
    revised_text = str(payload.get("text") or payload.get("narrative") or "").strip()
    return revised_text


def _apply_motif_governance_to_text(
    *,
    client: Any | None,
    draft_text: str,
    scene_card_now: Dict[str, Any],
    motifs_recent: List[str],
    sensory_palette: Dict[str, str],
    recent_events: List[str],
    audit_operation: str,
    revise_operation: str,
) -> tuple[str, Dict[str, Any]]:
    """Optionally run referee audit + one bounded narrator revise pass."""
    metadata: Dict[str, Any] = {
        "motif_referee_audit_enabled": bool(settings.enable_motif_referee_audit),
        "motif_referee_decision": "skipped",
    }
    cleaned_text = str(draft_text or "").strip()
    if not cleaned_text:
        return cleaned_text, metadata
    if client is None or not bool(settings.enable_motif_referee_audit):
        return cleaned_text, metadata

    revise_budget = max(0, min(1, int(settings.motif_referee_revise_budget)))
    if revise_budget <= 0:
        metadata["motif_referee_decision"] = "disabled_budget"
        return cleaned_text, metadata

    try:
        audit = _run_motif_referee_audit(
            client=client,
            draft_text=cleaned_text,
            scene_card_now=scene_card_now,
            motifs_recent=motifs_recent,
            sensory_palette=sensory_palette,
            recent_events=recent_events,
            operation=audit_operation,
        )
        metadata["motif_referee_decision"] = str(audit.get("decision", "ok"))
        metadata["motif_referee_overused"] = list(audit.get("overused_motifs", []))
        metadata["motif_referee_replacements"] = list(audit.get("replacement_anchors", []))
        if audit.get("decision") != "revise":
            return cleaned_text, metadata

        revised_text = _rewrite_text_with_motif_guidance(
            client=client,
            draft_text=cleaned_text,
            scene_card_now=scene_card_now,
            sensory_palette=sensory_palette,
            overused_motifs=list(audit.get("overused_motifs", [])),
            replacement_anchors=list(audit.get("replacement_anchors", [])),
            operation=revise_operation,
        )
        if revised_text:
            metadata["motif_referee_decision"] = "revised"
            return revised_text, metadata
        metadata["motif_referee_decision"] = "revise_no_text"
        return cleaned_text, metadata
    except Exception as exc:
        logger.debug("Motif governance audit/revise failed: %s", exc)
        metadata["motif_referee_decision"] = "audit_error"
        return cleaned_text, metadata


def _heuristic_adapt_storylet(
    storylet: Any,
    context: Dict[str, Any],
    base_choices: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Deterministic local adaptation used when AI is disabled/unavailable."""
    variables = context.get("variables", {})
    if not isinstance(variables, dict):
        variables = {}
    environment = context.get("environment", {})
    if not isinstance(environment, dict):
        environment = {}
    recent_events = [str(event).strip() for event in (context.get("recent_events") or [])[:_RUNTIME_ADAPT_EVENT_LIMIT] if str(event).strip()]

    base_text = _safe_render_template(str(getattr(storylet, "text_template", "")), variables)
    base_text = _fill_unresolved_placeholders(base_text, context)
    additions: List[str] = []

    if recent_events:
        additions.append(f"Recent events still echo: {recent_events[0]}.")

    weather = str(environment.get("weather", "")).strip().lower()
    if weather and weather != "clear":
        additions.append(f"The {weather} weather reshapes the mood of this moment.")

    danger_level = environment.get("danger_level")
    if isinstance(danger_level, (int, float)):
        if danger_level >= 7:
            additions.append("Tension crackles in the air as danger presses in from every side.")
        elif danger_level >= 4:
            additions.append("A steady undercurrent of risk shadows each decision.")

    adapted_text = " ".join(part.strip() for part in [base_text, *additions] if part).strip()
    adapted_choices = deepcopy(base_choices)

    if recent_events:
        event_lower = recent_events[0].lower()
        for choice in adapted_choices:
            label = str(choice.get("label", "Continue"))
            label_lower = label.lower()
            if "merchant" in label_lower and "merchant" in event_lower and "cheat" in event_lower and "just cheated" not in label_lower:
                choice["label"] = f"{label} you just cheated"

    return {"text": adapted_text, "choices": adapted_choices}


def adapt_storylet_to_context(storylet: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    """Expand a selected storylet to reflect recent state, events, and environment."""
    variables = context.get("variables", {})
    if not isinstance(variables, dict):
        variables = {}
    base_choices = _normalize_adaptation_choices(getattr(storylet, "choices", []))
    base_text = _safe_render_template(str(getattr(storylet, "text_template", "")), variables)
    base_text = _fill_unresolved_placeholders(base_text, context)

    if not settings.enable_runtime_adaptation:
        return {"text": base_text, "choices": base_choices}

    if is_ai_disabled():
        return _heuristic_adapt_storylet(storylet, context, base_choices)

    client = get_llm_client()
    if not client:
        return _heuristic_adapt_storylet(storylet, context, base_choices)

    recent_events = [str(event).strip() for event in (context.get("recent_events") or [])[:_RUNTIME_ADAPT_EVENT_LIMIT] if str(event).strip()]
    environment = context.get("environment", {})
    if not isinstance(environment, dict):
        environment = {}
    scene_card_now = context.get("scene_card_now", {})
    if not isinstance(scene_card_now, dict):
        scene_card_now = {}
    goal_lens = context.get("goal_lens", {})
    if not isinstance(goal_lens, dict):
        goal_lens = {}
    motifs_recent = _normalize_recent_motifs(context.get("motifs_recent", []), limit=40)
    sensory_palette = _normalize_sensory_palette(context.get("sensory_palette", {}))
    if not sensory_palette:
        sensory_palette = _normalize_sensory_palette(prompt_library.build_scene_card_sensory_palette(scene_card_now))

    try:
        response = _chat_completion_with_retry(
            client,
            metric_operation="adapt_storylet_to_context",
            model=get_narrator_model(),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": prompt_library.build_adaptation_prompt(),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "instruction": ("Expand this storylet to reflect current world context while keeping " "the original scene intent and choice meaning."),
                            "storylet": {
                                "title": str(getattr(storylet, "title", "")),
                                "text_template": str(getattr(storylet, "text_template", "")),
                                "choices": base_choices,
                            },
                            "context": {
                                "variables": variables,
                                "environment": environment,
                                "recent_events": recent_events,
                                "scene_card_now": scene_card_now,
                                "goal_lens": goal_lens,
                                "motifs_recent": motifs_recent,
                                "sensory_palette": sensory_palette,
                            },
                            "output_contract": {
                                "text": "string",
                                "choice_labels": ["string"],
                            },
                        },
                        default=str,
                    ),
                },
            ],
            temperature=min(0.9, settings.llm_temperature),
            max_tokens=min(900, settings.llm_max_tokens),
            timeout=settings.llm_timeout_seconds,
        )
        payload = _extract_json_object(response.choices[0].message.content or "{}")
        adapted_text = str(payload.get("text") or payload.get("narrative") or base_text).strip()
        if not adapted_text:
            adapted_text = base_text
        adapted_text = _fill_unresolved_placeholders(adapted_text, context)
        adapted_text, governance_meta = _apply_motif_governance_to_text(
            client=client,
            draft_text=adapted_text,
            scene_card_now=scene_card_now,
            motifs_recent=motifs_recent,
            sensory_palette=sensory_palette,
            recent_events=recent_events,
            audit_operation="adapt_storylet_motif_audit",
            revise_operation="adapt_storylet_motif_revise",
        )
        adapted_text = _fill_unresolved_placeholders(adapted_text, context)

        adapted_choices = deepcopy(base_choices)
        raw_labels = payload.get("choice_labels")
        if isinstance(raw_labels, list):
            for idx, label in enumerate(raw_labels[: len(adapted_choices)]):
                label_text = str(label or "").strip()
                if label_text:
                    adapted_choices[idx]["label"] = label_text
        elif isinstance(payload.get("choices"), list):
            for idx, choice in enumerate(payload["choices"][: len(adapted_choices)]):
                if isinstance(choice, dict):
                    label_text = str(choice.get("label") or "").strip()
                    if label_text:
                        adapted_choices[idx]["label"] = label_text

        return {
            "text": adapted_text,
            "choices": adapted_choices,
            "motif_governance": governance_meta,
        }
    except Exception as exc:
        logger.debug("Runtime storylet adaptation failed, using heuristic: %s", exc)
        return _heuristic_adapt_storylet(storylet, context, base_choices)


async def adapt_storylet_to_context_non_blocking(
    storylet: Any,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Async wrapper that offloads adaptation work from the event loop."""

    return await run_inference_thread(adapt_storylet_to_context, storylet, context)


def generate_contextual_storylets(current_vars: Dict[str, Any], n: int = 3) -> List[Dict[str, Any]]:
    """
    Generate storylets that are contextually relevant to the current game state.

    Args:
        current_vars: Current game variables/state
        n: Number of storylets to generate

    Returns:
        List of contextually relevant storylet dictionaries
    """
    # Extract context from current variables
    themes = []
    location = current_vars.get("location", "unknown")
    danger_level = current_vars.get("danger", 0)
    selected_theme = ""
    for key in ("world_theme", "theme", "starting_theme", "story_theme"):
        raw = current_vars.get(key)
        if isinstance(raw, str) and raw.strip():
            selected_theme = raw.strip()
            break

    selected_character = ""
    for key in ("player_role", "character_profile", "character", "starting_character"):
        raw = current_vars.get(key)
        if isinstance(raw, str) and raw.strip():
            selected_character = raw.strip()
            break

    # Determine themes based on current state
    if danger_level > 2:
        themes.extend(["danger", "survival", "tension", "escape"])
    elif danger_level < 1:
        themes.extend(["exploration", "discovery", "mystery", "preparation"])
    else:
        themes.extend(["adventure", "decision", "progress", "challenge"])

    # Add location-based themes and logical connections
    location_str = str(location).lower()
    if "void" in location_str or "cosmic" in location_str:
        themes.extend(["cosmic", "ethereal", "energy", "resonance"])
    elif "observatory" in location_str:
        themes.extend(["stellar", "observation", "cosmic_knowledge", "dimensions"])
    elif "nexus" in location_str:
        themes.extend(["social", "weaving", "information", "convergence"])

    if selected_theme:
        normalized_theme = re.sub(r"[^a-z0-9]+", "_", selected_theme.lower()).strip("_")
        if normalized_theme:
            themes.append(normalized_theme[:40])
        themes.append("player_defined_theme")

    if selected_character:
        normalized_character = re.sub(
            r"[^a-z0-9]+",
            "_",
            selected_character.lower(),
        ).strip("_")
        if normalized_character:
            themes.append(normalized_character[:40])
        themes.append("character_arc")

    deduped_themes: List[str] = []
    seen_themes: set[str] = set()
    for theme in themes:
        normalized = str(theme).strip().lower()
        if not normalized or normalized in seen_themes:
            continue
        seen_themes.add(normalized)
        deduped_themes.append(normalized)

    # Build a comprehensive contextual bible with story continuity
    bible = {
        "current_state": current_vars,
        "story_continuity": {
            "location": location,
            "danger_level": danger_level,
            "world_theme": selected_theme,
            "player_role": selected_character,
            "previous_actions": "Consider the player's current situation",
            "logical_progression": True,
        },
        "connection_rules": {
            "location_transitions": {
                "cosmic_observatory": [
                    "stellar_nexus",
                    "void_chamber",
                    "resonance_hall",
                ],
                "void_chamber": ["dimensional_rift", "quantum_flux", "essence_pool"],
                "stellar_nexus": ["observatory", "weaving_circle", "cosmic_market"],
                "reality_forge": ["nexus", "workshop", "harmonic_sphere"],
            },
            "danger_progression": {
                "low": "Introduce new challenges or discoveries",
                "medium": "Present meaningful choices with clear consequences",
                "high": "Focus on survival and risk mitigation",
            },
        },
        "required_variables": list(current_vars.keys()),
        "player_setup": {
            "world_theme": selected_theme,
            "character_profile": selected_character,
        },
        "story_coherence": {
            "maintain_established_facts": True,
            "logical_cause_and_effect": True,
            "progressive_difficulty": True,
        },
    }

    return llm_suggest_storylets(n, deduped_themes, bible)


def _normalize_runtime_choices(raw_choices: Any) -> List[Dict[str, Any]]:
    """Normalize generated choice payloads into {label, set} objects."""
    normalized: List[Dict[str, Any]] = []
    if not isinstance(raw_choices, list):
        return normalized

    for choice in raw_choices[:_RUNTIME_SYNTHESIS_MAX_CHOICES]:
        if not isinstance(choice, dict):
            continue
        label = str(choice.get("label") or choice.get("text") or "Continue").strip()
        set_payload = choice.get("set") or choice.get("set_vars") or {}
        if not isinstance(set_payload, dict):
            set_payload = {}
        normalized.append({"label": label or "Continue", "set": set_payload})
    return normalized


def _validate_runtime_storylet_schema(item: Any, idx: int) -> Dict[str, Any]:
    """Validate one runtime synthesis storylet candidate."""
    if not isinstance(item, dict):
        raise ValueError(f"Runtime candidate at index {idx} is not an object")

    title = str(item.get("title", "")).strip()
    text_template = str(item.get("text_template") or item.get("text") or "").strip()
    if not title:
        raise ValueError(f"Runtime candidate at index {idx} missing title")
    if not text_template:
        raise ValueError(f"Runtime candidate '{title}' missing text_template/text")

    requires = item.get("requires", {})
    if not isinstance(requires, dict):
        requires = {}

    choices = _normalize_runtime_choices(item.get("choices"))
    if not choices:
        raise ValueError(f"Runtime candidate '{title}' has no valid choices")

    weight_raw = item.get("weight", 1.0)
    try:
        weight = max(0.01, float(weight_raw))
    except (TypeError, ValueError):
        weight = 1.0

    return {
        "title": title,
        "text_template": text_template,
        "requires": requires,
        "choices": choices,
        "weight": weight,
    }


def validate_runtime_storylet_candidates(
    payload: Any,
    *,
    max_candidates: int = 3,
) -> List[Dict[str, Any]]:
    """Validate runtime synthesis payload against expected JSON shape."""
    items: Any = payload
    if isinstance(payload, dict):
        items = payload.get("storylets", [])
    if not isinstance(items, list):
        raise ValueError("Runtime synthesis payload must be a list or {storylets: []}")

    limit = max(1, min(3, int(max_candidates or 1)))
    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(items[:limit]):
        normalized.append(_validate_runtime_storylet_schema(item, idx))

    if not normalized:
        raise ValueError("Runtime synthesis returned no valid candidates")
    return normalized


def _fallback_runtime_storylets(
    current_vars: Dict[str, Any],
    world_facts: List[str],
    goal_lens: Dict[str, Any],
    n: int,
) -> List[Dict[str, Any]]:
    """Deterministic runtime synthesis fallback for sparse contexts."""
    location = str(current_vars.get("location") or "start").strip() or "start"
    first_fact = str(world_facts[0]).strip() if world_facts else "The world feels unsettled."

    primary_goal = goal_lens.get("primary_goal", "") if isinstance(goal_lens, dict) else ""
    goal_clause = str(primary_goal).strip() if primary_goal else "press forward"
    count = max(1, min(3, int(n or 1)))

    generated: List[Dict[str, Any]] = []
    for idx in range(count):
        suffix = f" #{idx + 1}" if count > 1 else ""
        generated.append(
            {
                "title": f"Fresh lead at {location}{suffix}",
                "text_template": (f"{first_fact} A new path opens near {location} as you {goal_clause}."),
                "requires": {"location": location},
                "choices": [
                    {"label": "Investigate the lead", "set": {"danger": {"inc": 1}}},
                    {"label": "Proceed carefully", "set": {"focus": "cautious"}},
                ],
                "weight": 1.05,
            }
        )
    return generated


def generate_runtime_storylet_candidates(
    current_vars: Dict[str, Any],
    world_facts: List[str],
    goal_lens: Dict[str, Any],
    *,
    n: int = 2,
) -> List[Dict[str, Any]]:
    """Generate 1-3 runtime storylet candidates grounded in current context."""
    limit = max(1, min(3, int(n or 1)))

    if is_ai_disabled():
        return _fallback_runtime_storylets(current_vars, world_facts, goal_lens, limit)

    client = get_llm_client()
    if not client:
        return _fallback_runtime_storylets(current_vars, world_facts, goal_lens, limit)

    _runtime_sys, _runtime_user = prompt_library.build_runtime_synthesis_prompt(
        current_vars,
        world_facts,
        goal_lens,
        count=limit,
    )

    try:
        response = _chat_completion_with_retry(
            client,
            metric_operation="generate_runtime_storylet_candidates",
            model=get_narrator_model(),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": _runtime_sys,
                },
                {"role": "user", "content": _runtime_user},
            ],
            temperature=min(0.8, settings.llm_temperature),
            max_tokens=min(1200, settings.llm_max_tokens),
            timeout=settings.llm_timeout_seconds,
        )
        payload = extract_json_value(response.choices[0].message.content or "{}")
        return validate_runtime_storylet_candidates(payload, max_candidates=limit)
    except Exception as exc:
        logger.warning(
            "Runtime storylet synthesis failed (category=%s); using fallback: %s",
            _llm_json_error_category(exc),
            exc,
        )
        return _fallback_runtime_storylets(current_vars, world_facts, goal_lens, limit)


def llm_suggest_storylets(n: int, themes: List[str], bible: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate storylets using LLM with enhanced context awareness.

    Args:
        n: Number of storylets to generate
        themes: List of themes to incorporate
        bible: Dictionary of world/setting constraints and feedback

    Returns:
        List of storylet dictionaries
    """
    # Fast mode or disabled AI: always return local fallbacks to keep tests and dev snappy
    if is_ai_disabled():
        return _fallback_storylets_for_n(n)

    client = get_llm_client()
    if not client:
        return _fallback_storylets_for_n(n)

    # Build context-aware system prompt via prompt library
    system_prompt = prompt_library.build_storylet_system_prompt(bible)

    # Build enhanced user prompt with feedback integration
    user_prompt = {
        "request": f"Generate {n} unique storylets",
        "themes": themes,
        "world_context": bible,
        "feedback_integration": extract_feedback_requirements(bible),
        "requirements": "Each storylet should address identified gaps while maintaining narrative quality",
    }

    try:
        response = _chat_completion_with_retry(
            client,
            metric_operation="llm_suggest_storylets",
            model=get_narrator_model(),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )
        response_text = (response.choices[0].message.content or "").strip()
        return _extract_json_storylet_list(response_text)
    except Exception as e:
        logger.warning(
            "LLM suggest failed (category=%s), using fallback storylets: %s",
            _llm_json_error_category(e),
            e,
        )
        return _fallback_storylets_for_n(n)


def build_feedback_aware_prompt(bible: Dict[str, Any]) -> str:
    """Build a system prompt that incorporates storylet analysis feedback."""

    base_prompt = (
        "You are a master storyteller creating interconnected storylets for an interactive fiction game. "
        "Your goal is to create LOGICAL, COHERENT storylets that flow naturally from the player's current situation. "
        "\n\nSTORY CONTINUITY RULES:"
        "\n- Build upon the player's current location and situation logically"
        "\n- Create natural transitions between locations (don't teleport randomly)"
        "\n- Respect established danger levels and previous choices"
        "\n- Ensure choices lead to believable consequences"
        "\n- Maintain internal consistency within the story world"
    )

    # Add feedback-specific instructions
    feedback_additions = []

    if "urgent_need" in bible:
        feedback_additions.append(f"\n🚨 CRITICAL PRIORITY: {bible['urgent_need']}")
        feedback_additions.append(f"   Gap Analysis: {bible.get('gap_analysis', '')}")

    if "optimization_need" in bible:
        feedback_additions.append(f"\n🎯 OPTIMIZATION FOCUS: {bible['optimization_need']}")
        feedback_additions.append(f"   Improvement Opportunity: {bible.get('gap_analysis', '')}")

    if "location_need" in bible:
        feedback_additions.append(f"\n🗺️ LOCATION CONNECTIVITY: {bible['location_need']}")
        feedback_additions.append(f"   Flow Issue: {bible.get('gap_analysis', '')}")

    if "world_state_analysis" in bible:
        analysis = bible["world_state_analysis"]
        feedback_additions.append("\n📊 CURRENT STORY STATE:")
        feedback_additions.append(f"   - Total Content: {analysis.get('total_content', 0)} storylets")
        feedback_additions.append(f"   - Connectivity Health: {analysis.get('connectivity_health', 0):.1%}")
        if analysis.get("story_flow_issues"):
            feedback_additions.append(f"   - Flow Issues: {', '.join(analysis['story_flow_issues'])}")

    if "improvement_priorities" in bible and bible["improvement_priorities"]:
        feedback_additions.append("\n🎯 TOP IMPROVEMENT PRIORITIES:")
        for i, priority in enumerate(bible["improvement_priorities"][:3], 1):
            feedback_additions.append(f"   {i}. {priority.get('suggestion', 'Unknown priority')}")

    if "successful_patterns" in bible and bible["successful_patterns"]:
        feedback_additions.append("\n✅ MAINTAIN THESE SUCCESSFUL PATTERNS:")
        for pattern in bible["successful_patterns"]:
            feedback_additions.append(f"   - {pattern}")

    # Add technical requirements
    technical_prompt = (
        "\n\nSTRICT FORMAT REQUIREMENTS:"
        "\n- Output ONLY valid JSON with a top-level 'storylets' array"
        "\n- Each storylet MUST have: title, text_template, requires, choices, weight"
        "\n- text_template should use {variable} syntax for dynamic content"
        "\n- requires should specify conditions like {'location': 'cosmic_observatory'} or {'resonance': {'lte': 2}}"
        "\n- choices is an array with {label, set} where 'set' modifies variables"
        "\n- weight is a float (higher = more likely to appear)"
        "\n\nVARIABLE OPERATIONS:"
        "\n- Direct assignment: {'has_item': true, 'location': 'new_place'}"
        "\n- Numeric increment/decrement: {'danger': {'inc': 1}, 'gold': {'dec': 5}}"
        "\n- Operators in requires: {'health': {'gte': 10}, 'danger': {'lte': 3}}"
        "\n\nCREATIVE GUIDELINES:"
        "\n- Each storylet should feel like a natural continuation of the story"
        "\n- Include sensory details that match the location"
        "\n- Create meaningful choices with clear, logical consequences"
        "\n- Build tension through logical progression, not random events"
        "\n- Reference the current state meaningfully in the text"
        "\n- Use emojis sparingly for atmosphere (⛏️🕯️🍄👁️💎🚪)"
    )

    return base_prompt + "".join(feedback_additions) + technical_prompt


def extract_feedback_requirements(bible: Dict[str, Any]) -> Dict[str, Any]:
    """Extract specific requirements from feedback for the AI to focus on."""
    requirements = {}

    # Extract required choices/sets from feedback
    if "required_choice_example" in bible:
        requirements["must_include_choice_type"] = bible["required_choice_example"]

    if "required_requirement_example" in bible:
        requirements["must_include_requirement_type"] = bible["required_requirement_example"]

    if "connectivity_focus" in bible:
        requirements["primary_focus"] = bible["connectivity_focus"]

    # Extract variable ecosystem needs
    if "variable_ecosystem" in bible:
        ecosystem = bible["variable_ecosystem"]
        requirements["variable_priorities"] = {
            "create_sources_for": ecosystem.get("needs_sources", []),
            "create_usage_for": ecosystem.get("needs_usage", []),
            "maintain_flow_for": ecosystem.get("well_connected", []),
        }

    return requirements


def generate_learning_enhanced_storylets(db, current_vars: Dict[str, Any], n: int = 3) -> List[Dict[str, Any]]:
    """
    Generate storylets using AI learning from current storylet analysis.

    This function combines contextual generation with storylet gap analysis.
    """
    from .storylet_analyzer import get_ai_learning_context

    # Get AI learning context
    learning_context = get_ai_learning_context(db)

    # Enhance the bible with learning context
    enhanced_bible = {
        **learning_context,
        "current_state": current_vars,
        "story_continuity": {
            "location": current_vars.get("location", "unknown"),
            "danger_level": current_vars.get("danger", 0),
            "logical_progression": True,
        },
        "ai_instructions": ("Use the world_state_analysis to understand what's working and what needs improvement. " "Focus on addressing the improvement_priorities while maintaining successful_patterns. " "Create storylets that enhance variable_ecosystem connectivity and improve location_network flow."),
    }

    # Determine themes based on current state and learning context
    themes = []
    danger_level = current_vars.get("danger", 0)

    if danger_level > 2:
        themes.extend(["danger", "survival", "tension", "escape"])
    elif danger_level < 1:
        themes.extend(["exploration", "discovery", "mystery", "preparation"])
    else:
        themes.extend(["adventure", "decision", "progress", "challenge"])

    # Add themes based on improvement priorities
    for priority in learning_context.get("improvement_priorities", []):
        if priority.get("themes"):
            themes.extend(priority["themes"])

    return llm_suggest_storylets(n, themes, enhanced_bible)


def generate_world_storylets(
    description: str,
    theme: str,
    player_role: str = "adventurer",
    key_elements: List[str] | None = None,
    tone: str = "adventure",
    count: int = 15,
) -> List[Dict[str, Any]]:
    """Generate storylets via world bible -> referee contracts -> reducer -> narrator."""

    if key_elements is None:
        key_elements = []

    # Fast path: avoid network during tests or when AI is disabled
    if is_ai_disabled():
        return [
            {
                "title": f"A New {theme.title()} Beginning",
                "text": f"You arrive as a {player_role} in a world themed {theme}.",
                "choices": [
                    {
                        "label": "Explore the area",
                        "set": {"location": "start", "exploration": 1},
                    },
                    {"label": "Gather information", "set": {"knowledge": 1}},
                ],
                "requires": {"location": "start"},
                "weight": 1.0,
            }
        ]

    try:
        client = get_llm_client()
        if not client:
            raise RuntimeError("No LLM API key configured")

        world_bible = generate_world_bible(
            description=description,
            theme=theme,
            player_role=player_role,
            tone=tone,
        )

        referee_response = _chat_completion_with_retry(
            client,
            metric_operation="generate_world_storylets_referee_contracts",
            model=get_referee_model(),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": ("You are the Referee layer for interactive-fiction bootstrap. " "Return only JSON with key 'storylets' as an array of contracts. " "Each contract must include title, premise, requires (object), " "choices (array of {label,set}), and weight."),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "description": description,
                            "theme": theme,
                            "player_role": player_role,
                            "key_elements": key_elements,
                            "tone": tone,
                            "count": int(count),
                            "world_bible": world_bible,
                        },
                        default=str,
                    ),
                },
            ],
            temperature=max(0.0, min(1.0, float(settings.llm_referee_temperature))),
            max_tokens=min(2200, settings.llm_max_tokens),
            timeout=settings.llm_timeout_seconds,
        )
        referee_payload = extract_json_value(referee_response.choices[0].message.content or "{}")
        if isinstance(referee_payload, dict):
            raw_contracts = referee_payload.get("storylets", referee_payload.get("contracts", []))
        elif isinstance(referee_payload, list):
            raw_contracts = referee_payload
        else:
            raw_contracts = []
        reduced_contracts = _reduce_storylet_contracts(raw_contracts, count=int(count), theme=theme)

        narrator_response = _chat_completion_with_retry(
            client,
            metric_operation="generate_world_storylets_narrator_render",
            model=get_narrator_model(),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": ("You are the Narrator layer. Convert storylet contracts into playable storylets. " "Return only JSON with key 'storylets' as an array. " "Each storylet must include title, text, choices, requires, and weight."),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "theme": theme,
                            "player_role": player_role,
                            "tone": tone,
                            "world_bible": world_bible,
                            "storylet_contracts": reduced_contracts,
                        },
                        default=str,
                    ),
                },
            ],
            temperature=max(0.0, min(1.2, float(settings.llm_narrator_temperature))),
            max_tokens=min(4000, settings.llm_max_tokens),
            timeout=settings.llm_timeout_seconds,
        )
        narrated_storylets = _extract_json_storylet_list((narrator_response.choices[0].message.content or "").strip())

        normalized_storylets: List[Dict[str, Any]] = []
        for idx, contract in enumerate(reduced_contracts):
            narrated = narrated_storylets[idx] if idx < len(narrated_storylets) and isinstance(narrated_storylets[idx], dict) else {}
            choices = _normalize_storylet_choices(narrated.get("choices"))
            if not choices:
                choices = contract["choices"]
            text = str(narrated.get("text") or narrated.get("text_template") or contract["premise"]).strip() or contract["premise"]
            normalized_storylets.append(
                {
                    "title": contract["title"],
                    "text": text,
                    "choices": choices,
                    "requires": contract["requires"],
                    "weight": float(contract["weight"]),
                }
            )

        logger.info(
            "Generated %s world storylets for theme=%s via bible->referee->reducer->narrator pipeline",
            len(normalized_storylets),
            theme,
        )
        return normalized_storylets

    except Exception as e:
        logger.error(
            "Error generating world storylets (category=%s): %s",
            _llm_json_error_category(e),
            e,
        )
        return [
            {
                "title": "A New Beginning",
                "text": f"You find yourself in the world of {theme}. Your journey as a {player_role} begins here.",
                "choices": [
                    {"label": "Explore the area", "set": {"exploration": 1}},
                    {"label": "Gather information", "set": {"knowledge": 1}},
                ],
                "requires": {},
                "weight": 1.0,
            }
        ]


def generate_starting_storylet(world_description, available_locations: list, world_themes: list) -> dict:
    """Generate a perfect starting storylet based on the actual generated world."""

    # Fast path: avoid network during tests or when AI is disabled
    if os.getenv("DW_FAST_TEST") == "1" or os.getenv("DW_DISABLE_AI") == "1" or os.getenv("PYTEST_CURRENT_TEST"):
        return {
            "title": "A New Beginning",
            "text": f"You begin your adventure as a {{player_role}} in the world of {world_description.theme}.",
            "choices": [
                {
                    "label": "Begin your journey",
                    "set": {
                        "location": (available_locations[0] if available_locations else "start"),
                        "player_role": world_description.player_role,
                    },
                },
                {
                    "label": "Observe your surroundings",
                    "set": {
                        "location": (available_locations[1] if len(available_locations) > 1 else (available_locations[0] if available_locations else "start")),
                        "player_role": world_description.player_role,
                    },
                },
            ],
        }

    try:
        client = get_llm_client()
        if not client:
            raise RuntimeError("No LLM API key configured")

        # Build context about the generated world via prompt library
        _ss_sys, _ss_user = prompt_library.build_starting_storylet_prompt(
            world_description,
            available_locations,
            world_themes,
        )

        response = _chat_completion_with_retry(
            client,
            metric_operation="generate_starting_storylet",
            model=get_narrator_model(),
            messages=[
                {"role": "system", "content": _ss_sys},
                {"role": "user", "content": _ss_user},
            ],
            temperature=settings.llm_temperature,
            max_tokens=800,
            timeout=settings.llm_timeout_seconds,
        )

        response_text = (response.choices[0].message.content or "").strip()

        # Debug: log the raw response to understand what's happening
        logger.debug(f"🔍 DEBUG Starting Storylet: Raw response length: {len(response_text)}")
        logger.debug(f"🔍 DEBUG Starting Storylet: Full response: {response_text}")

        starting_data = _extract_json_object(response_text)

        # Validate and normalize
        normalized_starting = {
            "title": starting_data.get("title", "A New Beginning"),
            "text": starting_data.get(
                "text",
                f"You begin your adventure as a {{player_role}} in the world of {world_description.theme}.",
            ),
            "choices": starting_data.get(
                "choices",
                [
                    {
                        "label": "Begin your journey",
                        "set": {
                            "location": (available_locations[0] if available_locations else "start"),
                            "player_role": world_description.player_role,
                        },
                    }
                ],
            ),
        }

        logger.info(f"✅ Generated contextual starting storylet: '{normalized_starting['title']}'")
        return normalized_starting

    except Exception as e:
        logger.warning(
            "⚠️ Error generating starting storylet (category=%s), using fallback: %s",
            _llm_json_error_category(e),
            e,
        )
        # Fallback starting storylet
        return {
            "title": "A New Beginning",
            "text": f"You find yourself in the world of {world_description.theme}. Your adventure as a {world_description.player_role} begins now.",
            "choices": [
                {
                    "label": "Begin your journey",
                    "set": {
                        "location": (available_locations[0] if available_locations else "start"),
                        "player_role": world_description.player_role,
                    },
                },
                {
                    "label": "Take a moment to observe",
                    "set": {
                        "location": (available_locations[1] if len(available_locations) > 1 else (available_locations[0] if available_locations else "start")),
                        "player_role": world_description.player_role,
                    },
                },
            ],
        }


# ---------------------------------------------------------------------------
# JIT BEAT GENERATION — world bible + per-turn beat generator
# ---------------------------------------------------------------------------

_BIBLE_REQUIRED_KEYS = {"locations", "central_tension", "entry_point"}
_BEAT_REQUIRED_KEYS = {"text", "choices"}


def _fallback_world_bible(
    description: str,
    theme: str,
    player_role: str,
    tone: str,
) -> Dict[str, Any]:
    """Deterministic fallback bible when AI is disabled or generation fails."""
    return {
        "world_name": theme.title(),
        "locations": [
            {"name": "start", "description": f"The beginning of your {theme} journey."},
            {"name": "outskirts", "description": "The edges of the known world."},
        ],
        "npcs": [
            {"name": "The Guide", "role": "Mentor", "motivation": "Help travellers find their way."},
        ],
        "central_tension": f"A {player_role} must navigate a {tone} {theme} world and discover their purpose.",
        "entry_point": f"You step into the {theme} world, your role as {player_role} still fresh.",
    }


def generate_world_bible(
    description: str,
    theme: str,
    player_role: str = "adventurer",
    tone: str = "adventure",
) -> Dict[str, Any]:
    """Generate a compact world bible via LLM for the JIT beat pipeline.

    Returns a dict with keys: world_name, locations, npcs, central_tension, entry_point.
    Falls back to a deterministic stub if AI is disabled or generation fails.
    """
    if is_ai_disabled():
        logger.info("AI disabled — returning fallback world bible")
        return _fallback_world_bible(description, theme, player_role, tone)

    client = get_llm_client()
    model = get_narrator_model()
    system_prompt, user_prompt = prompt_library.build_world_bible_prompt(
        description=description,
        theme=theme,
        player_role=player_role,
        tone=tone,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    started = time.monotonic()
    attempt = 0
    try:
        response = _chat_completion_with_retry(
            client,
            model=model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=600,
            timeout=settings.llm_timeout_seconds,
            metric_operation="generate_world_bible",
        )
        attempt = getattr(response, "_attempt", 1)
        raw = response.choices[0].message.content or ""
        logger.info(
            "generate_world_bible raw response (first 500 chars): %.500s",
            raw,
        )
        parsed = _extract_json_object(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"World bible parse returned {type(parsed).__name__}, expected dict")
        missing = _BIBLE_REQUIRED_KEYS - parsed.keys()
        if missing:
            raise ValueError(f"World bible missing required keys: {missing}")
        locations = parsed.get("locations", [])
        if not isinstance(locations, list) or len(locations) == 0:
            raise ValueError("World bible 'locations' must be a non-empty list")
        duration_ms = (time.monotonic() - started) * 1000.0
        _log_llm_call_metrics(
            operation="generate_world_bible",
            model=model,
            duration_ms=duration_ms,
            status="ok",
            attempt=attempt,
            **_extract_token_usage(response),
        )
        logger.info(
            "Generated world bible: %s locations, tension: %.80s",
            len(locations),
            parsed.get("central_tension", ""),
        )
        return parsed
    except Exception as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        _log_llm_call_metrics(
            operation="generate_world_bible",
            model=model,
            duration_ms=duration_ms,
            status="error",
            attempt=attempt,
            error_type=(_llm_json_error_category(exc) if isinstance(exc, LLMJsonError) else type(exc).__name__),
        )
        logger.error(
            "generate_world_bible failed (%s / category=%s): %s — JIT pipeline will use deterministic fallback world bible",
            type(exc).__name__,
            _llm_json_error_category(exc),
            exc,
            exc_info=True,
        )
        return _fallback_world_bible(description, theme, player_role, tone)


def _fallback_beat(current_vars: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic beat returned when AI is disabled or beat generation fails."""
    location = str(current_vars.get("location", "the path ahead"))
    player_role = str(current_vars.get("player_role", "traveller"))
    return {
        "title": "A Moment of Stillness",
        "text": (f"The {location} stretches before you. " f"As {player_role}, you pause and take stock of your surroundings. " "Something stirs at the edge of your awareness — a choice waiting to be made."),
        "tension": "A quiet moment before the storm.",
        "unresolved_threads": ["The path ahead remains unwritten"],
        "choices": [
            {"label": "Press forward", "set": {"progress": {"inc": 1}}},
            {"label": "Observe carefully before moving", "set": {"awareness": {"inc": 1}}},
        ],
    }


def generate_next_beat(
    world_bible: Dict[str, Any],
    recent_events: List[str],
    current_vars: Dict[str, Any] | None = None,
    goal_lens: Dict[str, Any] | None = None,
    scene_card: Dict[str, Any] | None = None,
    motifs_recent: List[str] | None = None,
    sensory_palette: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """Generate the next narrative beat via LLM for the JIT pipeline.

    Accepts both legacy args (current_vars/goal_lens) and preferred
    scene_card input. Falls back deterministically on any generation failure.
    """
    effective_scene_card = scene_card if isinstance(scene_card, dict) else {}
    fallback_vars = current_vars if isinstance(current_vars, dict) else {}
    normalized_motifs_recent = _normalize_recent_motifs(motifs_recent or [], limit=40)
    normalized_sensory_palette = _normalize_sensory_palette(sensory_palette or {})
    if not normalized_sensory_palette:
        normalized_sensory_palette = _normalize_sensory_palette(prompt_library.build_scene_card_sensory_palette(effective_scene_card))

    if isinstance(goal_lens, dict):
        goal_primary = str(goal_lens.get("primary_goal", "")).strip()
        if goal_primary and "active_goal" not in effective_scene_card:
            effective_scene_card = dict(effective_scene_card)
            effective_scene_card["active_goal"] = goal_primary
        if "goal_urgency" not in effective_scene_card and goal_lens.get("urgency") is not None:
            effective_scene_card = dict(effective_scene_card)
            effective_scene_card["goal_urgency"] = goal_lens.get("urgency")
        if "goal_complication" not in effective_scene_card and goal_lens.get("complication") is not None:
            effective_scene_card = dict(effective_scene_card)
            effective_scene_card["goal_complication"] = goal_lens.get("complication")

    if is_ai_disabled():
        logger.info("AI disabled - returning fallback beat")
        return _fallback_beat(fallback_vars)

    client = get_llm_client()
    if not client:
        logger.warning("LLM client unavailable - returning fallback beat")
        return _fallback_beat(fallback_vars)

    model = get_narrator_model()
    system_prompt, user_prompt = prompt_library.build_beat_generation_prompt(
        world_bible=world_bible,
        recent_events=recent_events,
        scene_card=effective_scene_card,
        motifs_recent=normalized_motifs_recent,
        sensory_palette=normalized_sensory_palette,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    started = time.monotonic()
    attempt = 0
    try:
        response = _chat_completion_with_retry(
            client,
            model=model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=400,
            timeout=settings.llm_timeout_seconds,
            metric_operation="generate_next_beat",
        )
        attempt = getattr(response, "_attempt", 1)
        raw = response.choices[0].message.content or ""
        parsed = _extract_json_object(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"Beat parse returned {type(parsed).__name__}, expected dict")
        missing = _BEAT_REQUIRED_KEYS - parsed.keys()
        if missing:
            raise ValueError(f"Beat missing required keys: {missing}")
        text_value = str(parsed.get("text", "")).strip()
        if not text_value:
            raise ValueError("Beat 'text' is empty")
        text_value, governance_meta = _apply_motif_governance_to_text(
            client=client,
            draft_text=text_value,
            scene_card_now=effective_scene_card,
            motifs_recent=normalized_motifs_recent,
            sensory_palette=normalized_sensory_palette,
            recent_events=recent_events,
            audit_operation="generate_next_beat_motif_audit",
            revise_operation="generate_next_beat_motif_revise",
        )
        raw_choices = parsed.get("choices", [])
        choices = _normalize_adaptation_choices(raw_choices)
        if len(choices) < 2:
            raise ValueError(f"Beat has fewer than 2 valid choices (got {len(choices)})")
        duration_ms = (time.monotonic() - started) * 1000.0
        _log_llm_call_metrics(
            operation="generate_next_beat",
            model=model,
            duration_ms=duration_ms,
            status="ok",
            attempt=attempt,
            **_extract_token_usage(response),
        )
        return {
            "title": str(parsed.get("title", "")).strip() or "Untitled Scene",
            "text": text_value,
            "tension": str(parsed.get("tension", "")).strip(),
            "unresolved_threads": [str(t) for t in parsed.get("unresolved_threads", [])][:3],
            "choices": choices,
            "motif_governance": governance_meta,
        }
    except Exception as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        _log_llm_call_metrics(
            operation="generate_next_beat",
            model=model,
            duration_ms=duration_ms,
            status="error",
            attempt=attempt,
            error_type=(_llm_json_error_category(exc) if isinstance(exc, LLMJsonError) else type(exc).__name__),
        )
        logger.warning(
            "generate_next_beat failed (%s / category=%s), using fallback: %s",
            type(exc).__name__,
            _llm_json_error_category(exc),
            exc,
        )
        return _fallback_beat(fallback_vars)


async def generate_next_beat_non_blocking(
    *args: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Async wrapper that offloads beat generation work from the event loop."""

    return await run_inference_thread(generate_next_beat, *args, **kwargs)


# ---------------------------------------------------------------------------
# Projection referee scoring
# ---------------------------------------------------------------------------


def score_projection_nodes(
    nodes: List[Dict[str, Any]],
    world_context: Dict[str, Any],
    *,
    timeout_seconds: Optional[float] = None,
    return_meta: bool = False,
) -> List[Dict[str, Any]] | tuple[List[Dict[str, Any]], bool]:
    """Score projection nodes for plausibility using the referee LLM lane.

    Falls back to deterministic scoring when AI is disabled or the call fails.
    Updates each node's ``confidence`` and ``allowed`` fields in-place.
    """
    from .llm_client import get_referee_model

    def _result(
        items: List[Dict[str, Any]],
        referee_scored: bool,
    ) -> List[Dict[str, Any]] | tuple[List[Dict[str, Any]], bool]:
        if return_meta:
            return items, referee_scored
        return items

    def _deterministic_fallback(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for node in items:
            sem = node.get("semantic_score")
            if sem is not None and isinstance(sem, (int, float)):
                node["confidence"] = round(min(1.0, max(0.0, float(sem) * 0.8 + 0.2)), 4)
            else:
                node["confidence"] = 0.6
            confidence = float(node.get("confidence", 0.0) or 0.0)
            node["allowed"] = bool(confidence >= 0.2)
        return items

    if not nodes:
        return _result(nodes, False)

    _deterministic_fallback(nodes)

    if is_ai_disabled() or not settings.enable_projection_referee_scoring:
        return _result(nodes, False)

    client = get_llm_client()
    if client is None:
        return _result(nodes, False)

    if timeout_seconds is not None and timeout_seconds <= 0.0:
        return _result(nodes, False)

    try:
        system_prompt, user_prompt = prompt_library.build_projection_referee_prompt(
            nodes,
            world_context,
        )
        model = get_referee_model()
        request_timeout = 10.0
        if timeout_seconds is not None:
            request_timeout = max(0.1, min(10.0, float(timeout_seconds)))
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.llm_referee_temperature,
            max_tokens=800,
            timeout=request_timeout,
        )
        raw_text = str(response.choices[0].message.content or "")
        scored = extract_json_array(raw_text)

        # Build lookup: node_id -> confidence (+ optional veto flag)
        score_map: Dict[str, float] = {}
        allowed_map: Dict[str, bool] = {}
        for entry in scored:
            if isinstance(entry, dict):
                nid = str(entry.get("node_id", ""))
                conf = entry.get("confidence")
                if nid and isinstance(conf, (int, float)):
                    score_map[nid] = round(min(1.0, max(0.0, float(conf))), 4)
                allowed = entry.get("allowed")
                if nid and isinstance(allowed, bool):
                    allowed_map[nid] = allowed

        # Apply referee scores
        scored_node_count = 0
        for node in nodes:
            nid = str(node.get("node_id", ""))
            if nid in score_map:
                node["confidence"] = score_map[nid]
                if nid in allowed_map:
                    node["allowed"] = bool(allowed_map[nid])
                else:
                    node["allowed"] = bool(float(node["confidence"]) >= 0.2)
                scored_node_count += 1

        return _result(nodes, scored_node_count > 0)

    except Exception as exc:
        logger.debug("Projection referee scoring failed (deterministic fallback): %s", exc)
        _deterministic_fallback(nodes)
        return _result(nodes, False)
