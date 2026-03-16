"""Shared freeform turn orchestration helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any, Dict

from sqlalchemy.orm import Session

from ...config import settings
from .timing import record_timing

_SEMANTIC_GOAL_PATTERN = re.compile(
    r"\b(?:looking for|look for|find|search for|seeking|where(?:'s| is))\s+(?:the\s+)?([a-z][a-z0-9 _-]{1,60})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FreeformInterpretationOutcome:
    result: Any
    staged_ack_line: str
    used_staged_pipeline: bool
    semantic_goal: str | None


def extract_semantic_goal(action: str) -> str | None:
    match = _SEMANTIC_GOAL_PATTERN.search(str(action or ""))
    if not match:
        return None
    goal = match.group(1).strip(" .,!?:;-")
    return goal or None


def quick_ack_line(action: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(action or "").strip())
    if len(cleaned) > 110:
        cleaned = f"{cleaned[:107]}..."
    return f'You commit to: "{cleaned}".'


def resolve_freeform_action_interpretation(
    *,
    action_text: str,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Any,
    db: Session,
    scene_card_now: Dict[str, Any],
    timings_ms: Dict[str, float] | None = None,
    ack_line_hint: str | None = None,
    strict_nonstaged_timing_key: str = "interpret_action_intent",
) -> FreeformInterpretationOutcome:
    from .. import action_validation_policy, command_interpreter

    staged_ack_line = ack_line_hint or quick_ack_line(action_text)
    strict_three_layer = bool(settings.enable_strict_three_layer_architecture)
    used_staged_pipeline = False
    result = None

    if settings.enable_staged_action_pipeline:
        intent_started = time.perf_counter()
        staged_intent = command_interpreter.interpret_action_intent(
            action=action_text,
            state_manager=state_manager,
            world_memory_module=world_memory_module,
            current_storylet=current_storylet,
            db=db,
            scene_card_now=scene_card_now,
        )
        record_timing(timings_ms, "interpret_action_intent", intent_started)
        if staged_intent is not None:
            staged_intent = action_validation_policy.validate_action_intent(
                intent=staged_intent,
                action_text=action_text,
                state_manager=state_manager,
                world_memory_module=world_memory_module,
                db=db,
            )
            used_staged_pipeline = True
            staged_ack_line = staged_intent.ack_line or staged_ack_line
            result = staged_intent.result
        elif strict_three_layer:
            metadata = {
                "validation_warnings": ["stage_a_unavailable_using_deterministic_planner_fallback"],
                "staged_pipeline": "intent",
            }
            result = command_interpreter.ActionResult(
                narrative_text=staged_ack_line,
                state_deltas={},
                should_trigger_storylet=False,
                follow_up_choices=[{"label": "Continue", "set": {}}],
                plausible=True,
                reasoning_metadata=metadata,
            )
            used_staged_pipeline = True
        else:
            fallback_started = time.perf_counter()
            result = command_interpreter.interpret_action(
                action=action_text,
                state_manager=state_manager,
                world_memory_module=world_memory_module,
                current_storylet=current_storylet,
                db=db,
                scene_card_now=scene_card_now,
            )
            record_timing(timings_ms, "interpret_action_fallback", fallback_started)
    else:
        if strict_three_layer:
            intent_started = time.perf_counter()
            staged_intent = command_interpreter.interpret_action_intent(
                action=action_text,
                state_manager=state_manager,
                world_memory_module=world_memory_module,
                current_storylet=current_storylet,
                db=db,
                scene_card_now=scene_card_now,
            )
            if staged_intent is not None:
                staged_intent = action_validation_policy.validate_action_intent(
                    intent=staged_intent,
                    action_text=action_text,
                    state_manager=state_manager,
                    world_memory_module=world_memory_module,
                    db=db,
                )
                staged_ack_line = staged_intent.ack_line or staged_ack_line
                result = staged_intent.result
                used_staged_pipeline = True
            else:
                metadata = {
                    "validation_warnings": ["stage_a_unavailable_using_deterministic_planner_fallback"],
                    "staged_pipeline": "intent",
                }
                result = command_interpreter.ActionResult(
                    narrative_text=staged_ack_line,
                    state_deltas={},
                    should_trigger_storylet=False,
                    follow_up_choices=[{"label": "Continue", "set": {}}],
                    plausible=True,
                    reasoning_metadata=metadata,
                )
                used_staged_pipeline = True
            record_timing(timings_ms, strict_nonstaged_timing_key, intent_started)
        else:
            interpret_started = time.perf_counter()
            result = command_interpreter.interpret_action(
                action=action_text,
                state_manager=state_manager,
                world_memory_module=world_memory_module,
                current_storylet=current_storylet,
                db=db,
                scene_card_now=scene_card_now,
            )
            record_timing(timings_ms, "interpret_action", interpret_started)

    if result is None:
        raise RuntimeError("Action interpretation returned no result")

    semantic_goal = extract_semantic_goal(action_text)

    beats_started = time.perf_counter()
    for beat in result.suggested_beats:
        if isinstance(beat, dict):
            state_manager.add_narrative_beat(beat)
    record_timing(timings_ms, "apply_suggested_beats", beats_started)

    goal_started = time.perf_counter()
    if isinstance(result.reasoning_metadata, dict):
        raw_goal_update = result.reasoning_metadata.get("goal_update")
        if isinstance(raw_goal_update, dict):
            state_manager.apply_goal_update(raw_goal_update, source="action_interpreter")
    record_timing(timings_ms, "apply_goal_update", goal_started)

    return FreeformInterpretationOutcome(
        result=result,
        staged_ack_line=staged_ack_line,
        used_staged_pipeline=used_staged_pipeline,
        semantic_goal=semantic_goal,
    )
