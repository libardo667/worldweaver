"""LLM integration service for generating storylets."""

import logging
import os
import json
import re
import time
from copy import deepcopy
from typing import Any, Dict, List, Optional

from . import runtime_metrics
from .llm_client import get_llm_client, get_model, get_trace_id, is_ai_disabled
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
    payload: Dict[str, Any] = {
        "event": "llm_service_call_metrics",
        "component": "llm_service",
        "operation": operation,
        "trace_id": get_trace_id(),
        "model": model,
        "status": status,
        "duration_ms": round(max(0.0, float(duration_ms)), 3),
        "attempt": int(max(1, attempt)),
        "input_tokens": int(max(0, input_tokens)),
        "output_tokens": int(max(0, output_tokens)),
        "total_tokens": int(max(0, total_tokens)),
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


def _strip_markdown_code_fences(text: str) -> str:
    """Remove wrapping markdown code fences if present."""
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_json_value(text: str) -> Any:
    """Extract the first valid JSON value from raw model text."""
    cleaned = _strip_markdown_code_fences(text)
    if not cleaned:
        raise ValueError("LLM returned empty content")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", cleaned):
        start_idx = match.start()
        try:
            value, _ = decoder.raw_decode(cleaned[start_idx:])
            return value
        except json.JSONDecodeError:
            continue

    raise ValueError("No valid JSON found in model response")


def _validate_storylet_payload(items: Any) -> List[Dict[str, Any]]:
    """Validate and normalize a list of generated storylet-like objects."""
    if not isinstance(items, list):
        raise ValueError("Storylet payload must be a JSON array")

    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Storylet at index {idx} is not an object")

        title = str(item.get("title", "")).strip()
        text_template = str(item.get("text_template", "")).strip()
        text = str(item.get("text", "")).strip()

        if not title:
            raise ValueError(f"Storylet at index {idx} missing required 'title'")
        if not text_template and not text:
            raise ValueError(
                f"Storylet '{title}' missing required 'text_template' or 'text'"
            )

        normalized.append(item)

    return normalized


def _extract_json_storylet_list(text: str) -> List[Dict[str, Any]]:
    """Parse model output into a validated list of storylet-like dicts."""
    value = _extract_json_value(text)

    if isinstance(value, dict) and isinstance(value.get("storylets"), list):
        return _validate_storylet_payload(value["storylets"])
    return _validate_storylet_payload(value)


def _extract_json_object(text: str) -> Dict[str, Any]:
    """Parse model output into a JSON object."""
    value = _extract_json_value(text)
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object in model response")
    return value


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
    recent_events = [
        str(event).strip()
        for event in (context.get("recent_events") or [])[:_RUNTIME_ADAPT_EVENT_LIMIT]
        if str(event).strip()
    ]

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
            if (
                "merchant" in label_lower
                and "merchant" in event_lower
                and "cheat" in event_lower
                and "just cheated" not in label_lower
            ):
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

    recent_events = [
        str(event).strip()
        for event in (context.get("recent_events") or [])[:_RUNTIME_ADAPT_EVENT_LIMIT]
        if str(event).strip()
    ]
    environment = context.get("environment", {})
    if not isinstance(environment, dict):
        environment = {}

    try:
        response = _chat_completion_with_retry(
            client,
            metric_operation="adapt_storylet_to_context",
            model=get_model(),
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
                            "instruction": (
                                "Expand this storylet to reflect current world context while keeping "
                                "the original scene intent and choice meaning."
                            ),
                            "storylet": {
                                "title": str(getattr(storylet, "title", "")),
                                "text_template": str(getattr(storylet, "text_template", "")),
                                "choices": base_choices,
                            },
                            "context": {
                                "variables": variables,
                                "environment": environment,
                                "recent_events": recent_events,
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

        return {"text": adapted_text, "choices": adapted_choices}
    except Exception as exc:
        logger.debug("Runtime storylet adaptation failed, using heuristic: %s", exc)
        return _heuristic_adapt_storylet(storylet, context, base_choices)


def generate_contextual_storylets(
    current_vars: Dict[str, Any], n: int = 3
) -> List[Dict[str, Any]]:
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
    active_goal: Optional[str],
    n: int,
) -> List[Dict[str, Any]]:
    """Deterministic runtime synthesis fallback for sparse contexts."""
    location = str(current_vars.get("location") or "start").strip() or "start"
    first_fact = str(world_facts[0]).strip() if world_facts else "The world feels unsettled."
    goal_clause = str(active_goal).strip() if active_goal else "press forward"
    count = max(1, min(3, int(n or 1)))

    generated: List[Dict[str, Any]] = []
    for idx in range(count):
        suffix = f" #{idx + 1}" if count > 1 else ""
        generated.append(
            {
                "title": f"Fresh lead at {location}{suffix}",
                "text_template": (
                    f"{first_fact} A new path opens near {location} as you {goal_clause}."
                ),
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
    active_goal: Optional[str],
    *,
    n: int = 2,
) -> List[Dict[str, Any]]:
    """Generate 1-3 runtime storylet candidates grounded in current context."""
    limit = max(1, min(3, int(n or 1)))

    if is_ai_disabled():
        return _fallback_runtime_storylets(current_vars, world_facts, active_goal, limit)

    client = get_llm_client()
    if not client:
        return _fallback_runtime_storylets(current_vars, world_facts, active_goal, limit)

    _runtime_sys, _runtime_user = prompt_library.build_runtime_synthesis_prompt(
        current_vars, world_facts, active_goal, count=limit,
    )

    try:
        response = _chat_completion_with_retry(
            client,
            metric_operation="generate_runtime_storylet_candidates",
            model=get_model(),
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
        payload = _extract_json_value(response.choices[0].message.content or "{}")
        return validate_runtime_storylet_candidates(payload, max_candidates=limit)
    except Exception as exc:
        logger.warning("Runtime storylet synthesis failed; using fallback: %s", exc)
        return _fallback_runtime_storylets(current_vars, world_facts, active_goal, limit)


def llm_suggest_storylets(
    n: int, themes: List[str], bible: Dict[str, Any]
) -> List[Dict[str, Any]]:
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
            model=get_model(),
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
        logger.warning("LLM suggest failed, using fallback storylets: %s", e)
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
        feedback_additions.append(
            f"\n🎯 OPTIMIZATION FOCUS: {bible['optimization_need']}"
        )
        feedback_additions.append(
            f"   Improvement Opportunity: {bible.get('gap_analysis', '')}"
        )

    if "location_need" in bible:
        feedback_additions.append(
            f"\n🗺️ LOCATION CONNECTIVITY: {bible['location_need']}"
        )
        feedback_additions.append(f"   Flow Issue: {bible.get('gap_analysis', '')}")

    if "world_state_analysis" in bible:
        analysis = bible["world_state_analysis"]
        feedback_additions.append(f"\n📊 CURRENT STORY STATE:")
        feedback_additions.append(
            f"   - Total Content: {analysis.get('total_content', 0)} storylets"
        )
        feedback_additions.append(
            f"   - Connectivity Health: {analysis.get('connectivity_health', 0):.1%}"
        )
        if analysis.get("story_flow_issues"):
            feedback_additions.append(
                f"   - Flow Issues: {', '.join(analysis['story_flow_issues'])}"
            )

    if "improvement_priorities" in bible and bible["improvement_priorities"]:
        feedback_additions.append(f"\n🎯 TOP IMPROVEMENT PRIORITIES:")
        for i, priority in enumerate(bible["improvement_priorities"][:3], 1):
            feedback_additions.append(
                f"   {i}. {priority.get('suggestion', 'Unknown priority')}"
            )

    if "successful_patterns" in bible and bible["successful_patterns"]:
        feedback_additions.append(f"\n✅ MAINTAIN THESE SUCCESSFUL PATTERNS:")
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
        requirements["must_include_requirement_type"] = bible[
            "required_requirement_example"
        ]

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


def generate_learning_enhanced_storylets(
    db, current_vars: Dict[str, Any], n: int = 3
) -> List[Dict[str, Any]]:
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
        "ai_instructions": (
            "Use the world_state_analysis to understand what's working and what needs improvement. "
            "Focus on addressing the improvement_priorities while maintaining successful_patterns. "
            "Create storylets that enhance variable_ecosystem connectivity and improve location_network flow."
        ),
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
    """Generate a complete storylet ecosystem from a world description."""

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

        # Build the world generation prompt via prompt library
        _wg_sys, _wg_user = prompt_library.build_world_gen_system_prompt(
            description, theme, player_role, key_elements, tone, count,
        )

        response = _chat_completion_with_retry(
            client,
            metric_operation="generate_world_storylets",
            model=get_model(),
            messages=[
                {"role": "system", "content": _wg_sys},
                {"role": "user", "content": _wg_user},
            ],
            temperature=0.8,  # More creative for world building
            max_tokens=4000,
            timeout=settings.llm_timeout_seconds,
        )

        response_text = (response.choices[0].message.content or "").strip()

        # Debug: log the raw response to understand what's happening
        logger.debug(f"🔍 DEBUG: Raw response length: {len(response_text)}")
        logger.debug(f"🔍 DEBUG: Full response: {response_text}")
        storylets = _extract_json_storylet_list(response_text)

        # Validate and normalize the storylets
        normalized_storylets = []
        for storylet in storylets:
            normalized = {
                "title": storylet.get("title", "Untitled Adventure"),
                "text": storylet.get("text", "An adventure awaits..."),
                "choices": storylet.get("choices", [{"label": "Continue", "set": {}}]),
                "requires": storylet.get("requires", {}),
                "weight": float(storylet.get("weight", 1.0)),
            }

            # Ensure choices have proper format
            normalized_choices = []
            for choice in normalized["choices"]:
                normalized_choice = {
                    "label": choice.get("label") or choice.get("text", "Continue"),
                    "set": choice.get("set") or choice.get("set_vars", {}),
                }
                normalized_choices.append(normalized_choice)

            normalized["choices"] = normalized_choices
            normalized_storylets.append(normalized)

        logger.info(
            f"✅ Generated {len(normalized_storylets)} world storylets for theme: {theme}"
        )
        return normalized_storylets

    except Exception as e:
        logger.error(f"❌ Error generating world storylets: {e}")
        # Return a fallback set of generic storylets
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


def generate_starting_storylet(
    world_description, available_locations: list, world_themes: list
) -> dict:
    """Generate a perfect starting storylet based on the actual generated world."""

    # Fast path: avoid network during tests or when AI is disabled
    if (
        os.getenv("DW_FAST_TEST") == "1"
        or os.getenv("DW_DISABLE_AI") == "1"
        or os.getenv("PYTEST_CURRENT_TEST")
    ):
        return {
            "title": "A New Beginning",
            "text": f"You begin your adventure as a {{player_role}} in the world of {world_description.theme}.",
            "choices": [
                {
                    "label": "Begin your journey",
                    "set": {
                        "location": (
                            available_locations[0] if available_locations else "start"
                        ),
                        "player_role": world_description.player_role,
                    },
                },
                {
                    "label": "Observe your surroundings",
                    "set": {
                        "location": (
                            available_locations[1]
                            if len(available_locations) > 1
                            else (
                                available_locations[0]
                                if available_locations
                                else "start"
                            )
                        ),
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
            world_description, available_locations, world_themes,
        )

        response = _chat_completion_with_retry(
            client,
            metric_operation="generate_starting_storylet",
            model=get_model(),
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
                            "location": (
                                available_locations[0]
                                if available_locations
                                else "start"
                            ),
                            "player_role": world_description.player_role,
                        },
                    }
                ],
            ),
        }

        logger.info(
            f"✅ Generated contextual starting storylet: '{normalized_starting['title']}'"
        )
        return normalized_starting

    except Exception as e:
        logger.warning(f"⚠️ Error generating starting storylet, using fallback: {e}")
        # Fallback starting storylet
        return {
            "title": "A New Beginning",
            "text": f"You find yourself in the world of {world_description.theme}. Your adventure as a {world_description.player_role} begins now.",
            "choices": [
                {
                    "label": "Begin your journey",
                    "set": {
                        "location": (
                            available_locations[0] if available_locations else "start"
                        ),
                        "player_role": world_description.player_role,
                    },
                },
                {
                    "label": "Take a moment to observe",
                    "set": {
                        "location": (
                            available_locations[1]
                            if len(available_locations) > 1
                            else (
                                available_locations[0]
                                if available_locations
                                else "start"
                            )
                        ),
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
    model = get_model()
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
            error_type=type(exc).__name__,
        )
        logger.error(
            "generate_world_bible failed (%s): %s — JIT pipeline will use deterministic fallback world bible",
            type(exc).__name__,
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
        "text": (
            f"The {location} stretches before you. "
            f"As {player_role}, you pause and take stock of your surroundings. "
            "Something stirs at the edge of your awareness — a choice waiting to be made."
        ),
        "choices": [
            {"label": "Press forward", "set": {"progress": {"inc": 1}}},
            {"label": "Observe carefully before moving", "set": {"awareness": {"inc": 1}}},
        ],
    }


def generate_next_beat(
    world_bible: Dict[str, Any],
    recent_events: List[str],
    current_vars: Dict[str, Any],
    story_arc: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate the next narrative beat via LLM for the JIT pipeline.

    Returns a dict with keys: title, text, choices.
    Falls back to a deterministic stub if AI is disabled or generation fails.
    """
    if is_ai_disabled():
        logger.info("AI disabled — returning fallback beat")
        return _fallback_beat(current_vars)

    client = get_llm_client()
    model = get_model()
    system_prompt, user_prompt = prompt_library.build_beat_generation_prompt(
        world_bible=world_bible,
        recent_events=recent_events,
        current_vars=current_vars,
        story_arc=story_arc,
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
        text = str(parsed.get("text", "")).strip()
        if not text:
            raise ValueError("Beat 'text' is empty")
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
            "text": text,
            "choices": choices,
        }
    except Exception as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        _log_llm_call_metrics(
            operation="generate_next_beat",
            model=model,
            duration_ms=duration_ms,
            status="error",
            attempt=attempt,
            error_type=type(exc).__name__,
        )
        logger.warning("generate_next_beat failed (%s), using fallback: %s", type(exc).__name__, exc)
        return _fallback_beat(current_vars)
