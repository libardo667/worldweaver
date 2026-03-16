"""Stage-A intent planning and shared action-context helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from ...config import settings
from ...models.schemas import ActionReasoningMetadata
from .. import prompt_library
from .types import ActionResult, StagedActionIntent

logger = logging.getLogger(__name__)

_MAX_FACTS_IN_CONTEXT = 8
_MAX_FACTS_IN_PROMPT = 5
_MAX_FACT_SNIPPET_CHARS = 180
_MAX_APPEND_FACTS = 5
_INTENT_MAX_TOKENS = 420


@dataclass(frozen=True)
class IntentDependencies:
    is_ai_disabled_fn: Callable[[], bool]
    extract_relevant_world_facts_fn: Callable[..., List[str]]
    detect_action_contradiction_fn: Callable[[str, List[str]], Optional[str]]
    goal_context_from_state_summary_fn: Callable[[Dict[str, Any]], str]
    heuristic_following_beats_fn: Callable[[str], List[Dict[str, Any]]]
    heuristic_goal_update_fn: Callable[[str, Dict[str, Any]], Optional[Dict[str, Any]]]
    collect_colocation_context_fn: Callable[..., List[Dict[str, Any]]]
    build_scene_card_payload_fn: Callable[[Any], Dict[str, Any]]
    build_sensory_palette_fn: Callable[[Dict[str, Any]], Dict[str, Any]]
    normalize_world_fact_snippets_fn: Callable[..., List[str]]
    join_world_fact_snippets_fn: Callable[[List[str]], str]
    canonical_location_rule_fn: Callable[[List[str]], str]
    extract_canonical_locations_fn: Callable[[Any], List[str]]
    sanitize_state_changes_fn: Callable[..., Dict[str, Any]]
    normalize_following_beats_fn: Callable[[Any, str], List[Dict[str, Any]]]
    sanitize_goal_update_fn: Callable[..., Optional[Dict[str, Any]]]
    coerce_number_fn: Callable[[Any], Optional[float]]
    truncate_text_fn: Callable[[Any, int], str]
    ack_line_for_action_fn: Callable[[str, Any], str]
    get_llm_client_fn: Callable[..., Any]
    shared_inference_policy_fn: Callable[..., Any]
    resolve_lane_model_fn: Callable[[Any], str]
    call_json_chat_completion_fn: Callable[..., Dict[str, Any]]
    llm_json_warning_fn: Callable[[Exception], List[str]]


def build_intent_prompt(
    action: str,
    scene_card_now: Dict[str, Any],
    recent_events: List[str],
    world_facts: List[str],
    *,
    deps: IntentDependencies,
    canonical_locations: Optional[List[str]] = None,
) -> str:
    """Build a compact stage-A prompt for intent + contract delta planning."""
    events_str = "; ".join(recent_events[:3]) if recent_events else "None"
    facts_str = deps.join_world_fact_snippets_fn(
        deps.normalize_world_fact_snippets_fn(
            world_facts,
            limit=_MAX_FACTS_IN_PROMPT,
            per_fact_chars=_MAX_FACT_SNIPPET_CHARS,
        )
    )

    return f"""Return stage-A intent JSON for this action.

CURRENT CONTEXT:
- Scene Card: {json.dumps(scene_card_now, ensure_ascii=False)}
- Recent events: {events_str}
- Known world facts: {facts_str}

PLAYER ACTION: "{action}"

JSON CONTRACT:
{{
  "ack_line": "single sentence immediate feedback",
  "plausible": true,
  "delta": {{
    "set": [{{"key": "string", "value": "any"}}],
    "increment": [{{"key": "string", "amount": 1}}],
    "append_fact": [{{"subject": "string", "predicate": "string", "value": "any"}}]
  }},
  "should_trigger_storylet": false,
  "following_beat": {{
    "name": "IncreasingTension",
    "intensity": 0.35,
    "turns": 3,
    "decay": 0.65
  }},
  "goal_update": {{
    "status": "progressed|complicated|derailed|branched|completed",
    "milestone": "short milestone",
    "urgency_delta": 0.0,
    "complication_delta": 0.0,
    "subgoal": "optional"
  }},
  "confidence": 0.7,
  "rationale": "short reasoning"
}}

Rules:
- Keep ack_line <= 160 chars.
- Only include concrete operations in delta.
- If implausible, set plausible=false and keep delta empty.
- Never include non-JSON text.{chr(10)}{deps.canonical_location_rule_fn(canonical_locations or [])}"""


def collect_action_context(
    *,
    action: str,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
    deps: IntentDependencies,
    scene_card_now: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Gather shared state/history/fact context used by action stages."""
    state_summary = state_manager.get_state_summary()
    current_text = None
    if current_storylet:
        current_text = str(getattr(current_storylet, "text_template", ""))

    recent_events: List[str] = []
    try:
        events = world_memory_module.get_world_history(
            db,
            session_id=state_manager.session_id,
            limit=5,
        )
        recent_events = [str(event.summary) for event in events if str(event.summary).strip()]
    except Exception:
        pass

    location = None
    variables = state_summary.get("variables", {})
    if isinstance(variables, dict):
        location = str(variables.get("location", "")) or None

    world_facts = deps.extract_relevant_world_facts_fn(
        world_memory_module=world_memory_module,
        db=db,
        session_id=state_manager.session_id,
        action=action,
        location=location,
    )
    contradiction = deps.detect_action_contradiction_fn(action, world_facts)
    goal_context = deps.goal_context_from_state_summary_fn(state_summary)
    heuristic_beats = deps.heuristic_following_beats_fn(action)
    heuristic_goal_update = deps.heuristic_goal_update_fn(action, state_summary)

    present_characters: List[Dict[str, Any]] = []
    if location:
        try:
            present_characters = deps.collect_colocation_context_fn(
                db=db,
                world_memory_module=world_memory_module,
                current_session_id=state_manager.session_id,
                location=location,
            )
        except Exception:
            pass

    if isinstance(scene_card_now, dict):
        scene_card_payload = dict(scene_card_now)
    else:
        scene_card_payload = deps.build_scene_card_payload_fn(state_manager)

    motifs_recent: List[str] = []
    if hasattr(state_manager, "get_recent_motifs"):
        try:
            motifs_recent = list(state_manager.get_recent_motifs(limit=40))
        except Exception:
            motifs_recent = []
    sensory_palette = deps.build_sensory_palette_fn(scene_card_payload)

    return {
        "state_summary": state_summary,
        "current_text": current_text,
        "recent_events": recent_events,
        "world_facts": world_facts,
        "contradiction": contradiction,
        "goal_context": goal_context,
        "heuristic_beats": heuristic_beats,
        "heuristic_goal_update": heuristic_goal_update,
        "scene_card_now": scene_card_payload,
        "motifs_recent": motifs_recent,
        "sensory_palette": sensory_palette,
        "present_characters": present_characters,
    }


def interpret_action_intent(
    action: str,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
    *,
    deps: IntentDependencies,
    scene_card_now: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    """Stage-A intent extraction with deterministic delta validation."""
    if deps.is_ai_disabled_fn():
        return None

    context = collect_action_context(
        action=action,
        state_manager=state_manager,
        world_memory_module=world_memory_module,
        current_storylet=current_storylet,
        db=db,
        deps=deps,
        scene_card_now=scene_card_now,
    )
    state_summary = context["state_summary"]
    world_facts = context["world_facts"]
    contradiction = context["contradiction"]
    heuristic_goal_update = context["heuristic_goal_update"]

    if contradiction:
        metadata = ActionReasoningMetadata(
            facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
            rejected_keys=[],
            validation_warnings=[],
            contradiction=contradiction,
            rationale="Action conflicts with existing persistent world facts.",
            goal_update=heuristic_goal_update,
            suggested_beats=[],
        ).model_dump(exclude_none=True)
        target = contradiction.split(" is already ")[0]
        status = contradiction.split(" is already ")[-1]
        result = ActionResult(
            narrative_text=(
                f"You try to {action.lower().rstrip('.')}, but the {target} is already {status}. "
                "You can only deal with the aftermath now."
            ),
            state_deltas={},
            should_trigger_storylet=False,
            follow_up_choices=[
                {"label": "Inspect the aftermath", "set": {}},
                {"label": "Change your plan", "set": {}},
            ],
            suggested_beats=[],
            plausible=False,
            reasoning_metadata=metadata,
        )
        return StagedActionIntent(
            ack_line=deps.ack_line_for_action_fn(action, "That clashes with what already happened."),
            result=result,
        )

    client = deps.get_llm_client_fn(
        policy=deps.shared_inference_policy_fn(state_manager, owner_id="action_intent"),
    )
    if not client:
        return None

    canonical_locations = deps.extract_canonical_locations_fn(state_manager)
    prompt = build_intent_prompt(
        action=action,
        scene_card_now=context["scene_card_now"],
        recent_events=context["recent_events"],
        world_facts=world_facts,
        deps=deps,
        canonical_locations=canonical_locations,
    )

    try:
        referee_model = deps.resolve_lane_model_fn(settings.llm_referee_model)
        payload = deps.call_json_chat_completion_fn(
            client=client,
            model=referee_model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": prompt_library.build_action_intent_system_prompt(),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=float(settings.llm_referee_temperature),
            max_tokens=min(_INTENT_MAX_TOKENS, int(settings.llm_max_tokens)),
            timeout=max(2, int(settings.llm_timeout_seconds)),
            operation="interpret_action_intent",
            frequency_penalty=float(settings.llm_referee_frequency_penalty),
            presence_penalty=float(settings.llm_referee_presence_penalty),
        )
    except Exception as exc:
        category = deps.llm_json_warning_fn(exc)
        logger.warning(
            "Stage-A intent failed (%s); using fallback path: %s",
            category[0] if category else "llm_error",
            exc,
        )
        return None

    rejected_keys: List[str] = []
    warnings: List[str] = []
    appended_facts: List[Dict[str, Any]] = []
    state_deltas = deps.sanitize_state_changes_fn(
        raw_state_changes={},
        raw_delta_contract=payload.get("delta"),
        state_summary=state_summary,
        rejected_keys=rejected_keys,
        warnings=warnings,
        appended_facts=appended_facts,
    )
    suggested_beats = deps.normalize_following_beats_fn(
        payload.get("following_beats", payload.get("following_beat")),
        action=action,
    )
    goal_update = deps.sanitize_goal_update_fn(
        payload.get("goal_update"),
        action=action,
        state_summary=state_summary,
    )
    confidence = deps.coerce_number_fn(payload.get("confidence"))
    if confidence is not None:
        confidence = max(0.0, min(1.0, confidence))
    rationale = deps.truncate_text_fn(payload.get("rationale"), max_len=400) or None
    plausible = bool(payload.get("plausible", True))
    should_trigger_storylet = bool(payload.get("should_trigger_storylet", False))
    ack_line = deps.ack_line_for_action_fn(action, payload.get("ack_line"))

    metadata = ActionReasoningMetadata(
        facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
        rejected_keys=rejected_keys[:30],
        validation_warnings=warnings[:30],
        confidence=confidence,
        rationale=rationale,
        goal_update=goal_update,
        appended_facts=appended_facts[:_MAX_APPEND_FACTS],
        suggested_beats=suggested_beats,
    ).model_dump(exclude_none=True)
    metadata["staged_pipeline"] = "intent"

    result = ActionResult(
        narrative_text=ack_line,
        state_deltas=state_deltas if plausible else {},
        should_trigger_storylet=should_trigger_storylet if plausible else False,
        follow_up_choices=[{"label": "Continue", "set": {}}],
        suggested_beats=suggested_beats if plausible else [],
        plausible=plausible,
        reasoning_metadata=metadata,
    )
    return StagedActionIntent(ack_line=ack_line, result=result)
