"""Stage-B narration helpers for the turn pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from ...config import settings
from .. import prompt_library
from ..llm_client import InferencePolicy

logger = logging.getLogger(__name__)

_MAX_FACTS_IN_PROMPT = 5
_MAX_FACT_SNIPPET_CHARS = 180
_MAX_FACT_PROMPT_CHARS = 900
_NARRATION_MAX_TOKENS = 720


@dataclass(frozen=True)
class NarrationDependencies:
    collect_action_context_fn: Callable[..., Dict[str, Any]]
    fallback_result_fn: Callable[[str], Any]
    is_ai_disabled_fn: Callable[[], bool]
    get_llm_client_fn: Callable[..., Any]
    shared_inference_policy_fn: Callable[[Any, str], InferencePolicy]
    resolve_lane_model_fn: Callable[[Any], str]
    call_json_chat_completion_fn: Callable[..., Dict[str, Any]]
    sanitize_follow_up_choices_fn: Callable[[Any, List[str]], List[Dict[str, Any]]]
    llm_json_warning_fn: Callable[[Exception], List[str]]
    truncate_text_fn: Callable[[Any, int], str]


def _truncate_text(value: Any, max_len: int = 1000) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        return text[:max_len]
    return text


def _actor_name_for_public_summary(state_manager: Any) -> str:
    for key in ("player_role", "player_name", "name"):
        raw_value = str(state_manager.get_variable(key) or "").strip()
        if not raw_value:
            continue
        if key == "player_role" and " — " in raw_value:
            raw_value = raw_value.split(" — ", 1)[0].strip()
        if raw_value:
            return raw_value[:120]
    return "Someone"


def _fallback_public_summary(
    *,
    action: str,
    resolved_movement_target: Optional[str],
    plausible: bool,
) -> str:
    cleaned = re.sub(r"\s+", " ", str(action or "").strip()).strip(" \"'")
    cleaned = cleaned.rstrip(".!?")
    if resolved_movement_target:
        target = str(resolved_movement_target or "").strip()
        if target:
            return f"Moves toward {target}."
    if not cleaned:
        return "Makes a small, outwardly readable adjustment."
    if cleaned.lower().startswith("i "):
        cleaned = cleaned[2:].strip()
    words = cleaned.split(" ", 1)
    verb = words[0].lower()
    rest = words[1] if len(words) > 1 else ""
    if verb in {"is", "has", "does"}:
        inflected = verb
    elif verb.endswith("y") and len(verb) > 1 and verb[-2] not in "aeiou":
        inflected = verb[:-1] + "ies"
    elif verb.endswith(("s", "sh", "ch", "x", "z", "o")):
        inflected = verb + "es"
    else:
        inflected = verb + "s"
    clause = inflected + (f" {rest}" if rest else "")
    clause = clause[:1].upper() + clause[1:] + "."
    if plausible:
        return clause
    return f"Tries to {cleaned.lower()}, but little visibly changes."


def _normalize_world_fact_snippets(
    world_facts: Optional[List[str]],
    *,
    limit: int,
    per_fact_chars: int,
) -> List[str]:
    snippets: List[str] = []
    seen: set[str] = set()
    for raw in world_facts or []:
        text = re.sub(r"\s+", " ", str(raw or "").strip())
        if not text:
            continue
        text = _truncate_text(text, max_len=per_fact_chars)
        if text in seen:
            continue
        seen.add(text)
        snippets.append(text)
        if len(snippets) >= limit:
            break
    return snippets


def _join_world_fact_snippets(snippets: List[str]) -> str:
    if not snippets:
        return "None"

    selected: List[str] = []
    used_chars = 0
    for snippet in snippets:
        separator_chars = 2 if selected else 0
        if used_chars + separator_chars + len(snippet) > _MAX_FACT_PROMPT_CHARS:
            break
        selected.append(snippet)
        used_chars += separator_chars + len(snippet)

    return "; ".join(selected) if selected else "None"


def build_narration_prompt(
    *,
    action: str,
    ack_line: str,
    validated_state_changes: Dict[str, Any],
    current_storylet_text: Optional[str],
    recent_events: List[str],
    world_facts: List[str],
    scene_card_now: Dict[str, Any],
    motifs_recent: List[str],
    sensory_palette: Dict[str, Any],
    actor_name: str,
    present_characters: Optional[List[Dict[str, Any]]] = None,
    resolved_movement_target: Optional[str] = None,
) -> str:
    """Build stage-B narration prompt from validated deltas only."""
    facts_str = _join_world_fact_snippets(
        _normalize_world_fact_snippets(
            world_facts,
            limit=_MAX_FACTS_IN_PROMPT,
            per_fact_chars=_MAX_FACT_SNIPPET_CHARS,
        )
    )
    events_str = "; ".join(recent_events[:4]) if recent_events else "None"

    causal_anchor = scene_card_now.get("recent_action_summary") or action

    present_str = ""
    if present_characters:
        lines = []
        for ch in present_characters:
            role = ch.get("role", "")
            last = ch.get("last_action", "")
            entry = role
            if last:
                entry += f" — last seen: {last[:120]}"
            lines.append(entry)
        present_str = "; ".join(lines)

    payload: Dict[str, Any] = {
        "instruction": (
            "Render narration and follow-up choices using only validated state changes. "
            "Do not invent new mutations."
        ),
        "recent_action_summary": causal_anchor,
        "ack_line": ack_line,
        "current_scene": current_storylet_text or "",
        "validated_state_changes": validated_state_changes,
        "scene_card_now": scene_card_now,
        "motifs_recent": motifs_recent,
        "sensory_palette": sensory_palette,
        "actor_name": actor_name,
        "recent_events": events_str,
        "known_world_facts": facts_str,
        "output_contract": {
            "narrative": "string",
            "public_summary": "string",
            "choices": [{"label": "string", "set": {}, "intent": "string"}],
        },
    }
    if present_str:
        payload["present_characters"] = present_str
    if resolved_movement_target:
        payload["resolved_movement_target"] = resolved_movement_target
        payload["instruction"] = (
            f"The player has just arrived at {resolved_movement_target}. "
            "Narrate the arrival at this new location vividly. "
            "Do not invent new state mutations beyond the validated changes."
        )
    return json.dumps(payload, default=str)


def render_validated_action_narration(
    *,
    action: str,
    ack_line: str,
    validated_result: Any,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
    deps: NarrationDependencies,
    scene_card_now: Optional[Dict[str, Any]] = None,
    resolved_movement_target: Optional[str] = None,
    inference_policy: InferencePolicy | None = None,
) -> Any:
    """Render Stage-B narration without mutating state."""
    context = deps.collect_action_context_fn(
        action=action,
        state_manager=state_manager,
        world_memory_module=world_memory_module,
        current_storylet=current_storylet,
        db=db,
        scene_card_now=None,
    )
    post_commit_scene = dict(context["scene_card_now"])
    post_commit_scene["recent_action_summary"] = ack_line or action
    context = dict(context)
    context["scene_card_now"] = post_commit_scene

    if not validated_result.plausible:
        return validated_result

    if deps.is_ai_disabled_fn():
        fallback = deps.fallback_result_fn(action)
        return type(validated_result)(
            narrative_text=fallback.narrative_text,
            public_summary=getattr(fallback, "public_summary", "") or _fallback_public_summary(
                action=action,
                resolved_movement_target=resolved_movement_target,
                plausible=bool(validated_result.plausible),
            ),
            state_deltas=validated_result.state_deltas,
            should_trigger_storylet=validated_result.should_trigger_storylet,
            follow_up_choices=fallback.follow_up_choices,
            suggested_beats=validated_result.suggested_beats,
            plausible=validated_result.plausible,
            reasoning_metadata=dict(validated_result.reasoning_metadata),
        )

    client = deps.get_llm_client_fn(
        policy=inference_policy or deps.shared_inference_policy_fn(state_manager, owner_id="action_narration"),
    )
    if not client:
        return validated_result

    prompt = build_narration_prompt(
        action=action,
        ack_line=ack_line,
        validated_state_changes=validated_result.state_deltas,
        current_storylet_text=context["current_text"],
        recent_events=context["recent_events"],
        world_facts=context["world_facts"],
        scene_card_now=context["scene_card_now"],
        motifs_recent=context["motifs_recent"],
        sensory_palette=context["sensory_palette"],
        actor_name=_actor_name_for_public_summary(state_manager),
        present_characters=context.get("present_characters"),
        resolved_movement_target=resolved_movement_target,
    )
    rejected_keys: List[str] = []
    try:
        narrator_model = deps.resolve_lane_model_fn(settings.llm_narrator_model)
        payload = deps.call_json_chat_completion_fn(
            client=client,
            model=narrator_model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": prompt_library.build_action_narration_system_prompt(),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=float(settings.llm_narrator_temperature),
            max_tokens=min(_NARRATION_MAX_TOKENS, int(settings.llm_max_tokens)),
            timeout=max(2, int(settings.llm_timeout_seconds)),
            operation="render_validated_action_narration",
            frequency_penalty=float(settings.llm_narrator_frequency_penalty),
            presence_penalty=float(settings.llm_narrator_presence_penalty),
        )
    except Exception as exc:
        category = deps.llm_json_warning_fn(exc)
        logger.warning(
            "Stage-B narration failed (%s); using validated fallback: %s",
            category[0] if category else "llm_error",
            exc,
        )
        metadata = dict(validated_result.reasoning_metadata)
        warnings = list(metadata.get("validation_warnings", []))
        warnings.append("stage_b_failed_fallback")
        warnings.extend(category)
        metadata["validation_warnings"] = warnings[:30]
        return type(validated_result)(
            narrative_text=validated_result.narrative_text,
            public_summary=validated_result.public_summary or _fallback_public_summary(
                action=action,
                resolved_movement_target=resolved_movement_target,
                plausible=bool(validated_result.plausible),
            ),
            state_deltas=validated_result.state_deltas,
            should_trigger_storylet=validated_result.should_trigger_storylet,
            follow_up_choices=validated_result.follow_up_choices,
            suggested_beats=validated_result.suggested_beats,
            plausible=validated_result.plausible,
            reasoning_metadata=metadata,
        )

    narrative = deps.truncate_text_fn(
        payload.get("narrative") or payload.get("text") or validated_result.narrative_text,
        max_len=1200,
    )
    public_summary = deps.truncate_text_fn(
        payload.get("public_summary")
        or validated_result.public_summary
        or _fallback_public_summary(
            action=action,
            resolved_movement_target=resolved_movement_target,
            plausible=bool(validated_result.plausible),
        ),
        max_len=240,
    )
    choices = deps.sanitize_follow_up_choices_fn(payload.get("choices", []), rejected_keys)
    metadata = dict(validated_result.reasoning_metadata)
    warnings = list(metadata.get("validation_warnings", []))
    attempted_mutation = False
    for key in ("state_changes", "delta", "set", "increment", "append_fact", "variables"):
        raw_value = payload.get(key)
        if isinstance(raw_value, dict) and raw_value:
            attempted_mutation = True
            break
        if isinstance(raw_value, list) and raw_value:
            attempted_mutation = True
            break
    if attempted_mutation:
        warnings.append("stage_b_state_mutation_ignored")
        logger.warning("Stage-B narrator attempted state mutation; ignored by contract.")
    warnings.extend([f"stage_b_choice_rejected:{key}" for key in rejected_keys[:10]])
    metadata["validation_warnings"] = warnings[:30]
    metadata["staged_pipeline"] = "narrate"
    return type(validated_result)(
        narrative_text=narrative,
        public_summary=public_summary,
        state_deltas=validated_result.state_deltas,
        should_trigger_storylet=validated_result.should_trigger_storylet,
        follow_up_choices=choices,
        suggested_beats=validated_result.suggested_beats,
        plausible=validated_result.plausible,
        reasoning_metadata=metadata,
    )
