"""Shared turn orchestration for /api/next and /api/action."""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Tuple, cast

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Storylet
from ..models.schemas import (
    ActionDeltaContract,
    ActionDeltaSetOperation,
    ActionRequest,
    ChoiceOut,
    NextReq,
    NextResp,
)
from .game_logic import ensure_storylets, render
from .llm_service import adapt_storylet_to_context, generate_next_beat
from .rules.reducer import reduce_event
from .rules.schema import (
    ChoiceSelectedIntent,
    FreeformActionCommittedIntent,
    SimulationTickIntent,
    SystemTickIntent,
)
from .session_service import get_spatial_navigator, get_state_manager, save_state
from .simulation.tick import tick_world_simulation
from .storylet_selector import pick_storylet_enhanced
from .storylet_utils import find_storylet_by_location, normalize_choice

logger = logging.getLogger(__name__)

_SEMANTIC_GOAL_PATTERN = re.compile(
    r"\b(?:looking for|look for|find|search for|seeking|where(?:'s| is))\s+(?:the\s+)?([a-z][a-z0-9 _-]{1,60})",
    re.IGNORECASE,
)


def _extract_semantic_goal(action: str) -> str | None:
    match = _SEMANTIC_GOAL_PATTERN.search(str(action or ""))
    if not match:
        return None
    goal = match.group(1).strip(" .,!?:;-")
    return goal or None


def _quick_ack_line(action: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(action or "").strip())
    if len(cleaned) > 110:
        cleaned = f"{cleaned[:107]}..."
    return f'You commit to: "{cleaned}".'


def _record_timing(
    timings_ms: Dict[str, float] | None,
    key: str,
    started: float,
) -> None:
    if timings_ms is None:
        return
    timings_ms[key] = round((time.perf_counter() - started) * 1000.0, 3)


class TurnOrchestrator:
    """One authoritative turn pipeline for next/action compatibility routes."""

    @staticmethod
    def process_action_turn(
        *,
        db: Session,
        payload: ActionRequest,
        timings_ms: Dict[str, float] | None = None,
        phase_events: List[Tuple[str, Dict[str, Any]]] | None = None,
        ack_line_hint: str | None = None,
        get_spatial_navigator_fn=get_spatial_navigator,
        pick_storylet_fn=pick_storylet_enhanced,
        render_fn=render,
        find_storylet_by_location_fn=find_storylet_by_location,
    ) -> Dict[str, Any]:
        """Interpret and commit one freeform action turn."""
        from . import action_validation_policy
        from . import command_interpreter
        from . import world_memory

        idempotency_key = str(payload.idempotency_key or "").strip()
        idempotency_started = time.perf_counter()
        if idempotency_key:
            replay = world_memory.get_action_idempotent_response(
                db=db,
                session_id=payload.session_id,
                idempotency_key=idempotency_key,
            )
            if replay is not None:
                _record_timing(timings_ms, "idempotency_lookup", idempotency_started)
                return replay
        _record_timing(timings_ms, "idempotency_lookup", idempotency_started)

        state_started = time.perf_counter()
        state_manager = get_state_manager(payload.session_id, db)
        _record_timing(timings_ms, "load_state_manager", state_started)

        location_started = time.perf_counter()
        current_location = str(state_manager.get_variable("location", "start"))
        current_storylet = find_storylet_by_location_fn(db, current_location)
        _record_timing(timings_ms, "resolve_current_storylet", location_started)

        staged_ack_line = ack_line_hint or _quick_ack_line(payload.action)
        used_staged_pipeline = False
        result = None

        if settings.enable_staged_action_pipeline:
            intent_started = time.perf_counter()
            staged_intent = command_interpreter.interpret_action_intent(
                action=payload.action,
                state_manager=state_manager,
                world_memory_module=world_memory,
                current_storylet=current_storylet,
                db=db,
            )
            _record_timing(timings_ms, "interpret_action_intent", intent_started)
            if staged_intent is not None:
                staged_intent = action_validation_policy.validate_action_intent(
                    intent=staged_intent,
                    action_text=payload.action,
                    state_manager=state_manager,
                    world_memory_module=world_memory,
                    db=db,
                )
                used_staged_pipeline = True
                staged_ack_line = staged_intent.ack_line or staged_ack_line
                result = staged_intent.result
            else:
                fallback_started = time.perf_counter()
                result = command_interpreter.interpret_action(
                    action=payload.action,
                    state_manager=state_manager,
                    world_memory_module=world_memory,
                    current_storylet=current_storylet,
                    db=db,
                )
                _record_timing(
                    timings_ms,
                    "interpret_action_fallback",
                    fallback_started,
                )
        else:
            interpret_started = time.perf_counter()
            result = command_interpreter.interpret_action(
                action=payload.action,
                state_manager=state_manager,
                world_memory_module=world_memory,
                current_storylet=current_storylet,
                db=db,
            )
            _record_timing(timings_ms, "interpret_action", interpret_started)

        if result is None:
            raise RuntimeError("Action interpretation returned no result")

        semantic_goal = _extract_semantic_goal(payload.action)

        beats_started = time.perf_counter()
        for beat in result.suggested_beats:
            if isinstance(beat, dict):
                state_manager.add_narrative_beat(beat)
        _record_timing(timings_ms, "apply_suggested_beats", beats_started)

        goal_started = time.perf_counter()
        goal_update = None
        if isinstance(result.reasoning_metadata, dict):
            raw_goal_update = result.reasoning_metadata.get("goal_update")
            if isinstance(raw_goal_update, dict):
                goal_update = raw_goal_update
        if goal_update:
            state_manager.apply_goal_update(goal_update, source="action_interpreter")
        _record_timing(timings_ms, "apply_goal_update", goal_started)

        event_type = world_memory.infer_event_type(
            world_memory.EVENT_TYPE_FREEFORM_ACTION,
            result.state_deltas,
        )

        applied_deltas: Dict[str, Any] = {}
        action_event_id: int | None = None
        record_event_started = time.perf_counter()
        try:
            delta_contract = ActionDeltaContract()
            for key, value in (result.state_deltas or {}).items():
                delta_contract.set.append(ActionDeltaSetOperation(key=key, value=value))

            intent = FreeformActionCommittedIntent(
                action_text=payload.action,
                delta=delta_contract,
            )
            receipt = reduce_event(db, state_manager, intent)
            tick_receipt = reduce_event(db, state_manager, SystemTickIntent())
            applied_deltas = {**receipt.applied_changes, **tick_receipt.applied_changes}

            event = world_memory.record_event(
                db=db,
                session_id=payload.session_id,
                storylet_id=cast(int, current_storylet.id) if current_storylet else None,
                event_type=event_type,
                summary=f"Player action: {payload.action}. Result: {result.narrative_text[:200]}",
                delta=applied_deltas,
                state_manager=None,
                metadata=result.reasoning_metadata,
                idempotency_key=idempotency_key or None,
            )
            action_event_id = int(event.id) if event.id is not None else None

            sim_delta = tick_world_simulation(state_manager)
            if sim_delta.increment or sim_delta.set or sim_delta.append_fact:
                sim_receipt = reduce_event(
                    db,
                    state_manager,
                    SimulationTickIntent(delta=sim_delta),
                )
                world_memory.record_event(
                    db=db,
                    session_id=payload.session_id,
                    storylet_id=cast(int, current_storylet.id) if current_storylet else None,
                    event_type=world_memory.EVENT_TYPE_SIMULATION_TICK,
                    summary="Deterministic world simulation tick",
                    delta=sim_receipt.applied_changes,
                    state_manager=None,
                )
        except Exception as exc:
            logger.warning("Failed to record action event: %s", exc)
        _record_timing(timings_ms, "record_action_event", record_event_started)

        triggered_text = None
        should_trigger = result.should_trigger_storylet or world_memory.should_trigger_storylet(
            event_type,
            result.state_deltas,
        )
        trigger_started = time.perf_counter()
        if should_trigger:
            contextual_vars = state_manager.get_contextual_variables()
            triggered = pick_storylet_fn(db, state_manager)
            if triggered:
                triggered_text = render_fn(cast(str, triggered.text_template), contextual_vars)
        _record_timing(timings_ms, "trigger_follow_up_storylet", trigger_started)

        validated_result = result
        if phase_events is not None:
            phase_events.append(
                (
                    "commit",
                    {
                        "plausible": bool(validated_result.plausible),
                        "state_changes": (validated_result.state_deltas if isinstance(validated_result.state_deltas, dict) else {}),
                    },
                )
            )

        final_result = validated_result
        if used_staged_pipeline and bool(validated_result.plausible):
            if phase_events is not None:
                phase_events.append(("narrate", {"status": "started"}))
            narrate_started = time.perf_counter()
            final_result = command_interpreter.render_validated_action_narration(
                action=payload.action,
                ack_line=staged_ack_line,
                validated_result=validated_result,
                state_manager=state_manager,
                world_memory_module=world_memory,
                current_storylet=current_storylet,
                db=db,
            )
            _record_timing(timings_ms, "render_action_narration", narrate_started)

        choices_started = time.perf_counter()
        raw_choices = final_result.follow_up_choices if isinstance(final_result.follow_up_choices, list) else []
        choices = []
        for choice in raw_choices[:3]:
            if not isinstance(choice, dict):
                continue
            choice_set = choice.get("set", {})
            if not isinstance(choice_set, dict):
                choice_set = {}
            choices.append(
                {
                    "label": str(choice.get("label", "Continue")),
                    "set": choice_set,
                }
            )
        if not choices:
            choices = [{"label": "Continue", "set": {}}]
        _record_timing(timings_ms, "normalize_choices", choices_started)

        arc_started = time.perf_counter()
        state_manager.advance_story_arc(choices_made=choices)
        _record_timing(timings_ms, "advance_story_arc", arc_started)

        state_changes = final_result.state_deltas if isinstance(final_result.state_deltas, dict) else {}
        narrative_text = str(final_result.narrative_text or "")
        hint_started = time.perf_counter()
        if semantic_goal:
            try:
                from .semantic_selector import compute_player_context_vector

                spatial_nav = get_spatial_navigator_fn(db)
                effective_storylet = current_storylet
                if effective_storylet is None:
                    positioned_ids = list(spatial_nav.storylet_positions.keys())
                    if positioned_ids:
                        effective_storylet = db.query(Storylet).filter(Storylet.id.in_(positioned_ids)).first()
                if effective_storylet is None:
                    raise ValueError("No positioned storylet available for semantic hint")

                context_vector = compute_player_context_vector(
                    state_manager,
                    world_memory,
                    db,
                )
                goal_hint = spatial_nav.get_semantic_goal_hint(
                    current_storylet_id=cast(int, effective_storylet.id),
                    player_vars=state_manager.get_contextual_variables(),
                    semantic_goal=semantic_goal,
                    context_vector=context_vector,
                )
                if goal_hint and goal_hint.get("hint"):
                    narrative_text = f"{narrative_text} {goal_hint['hint']}".strip()
            except Exception as exc:
                logger.debug("Could not resolve semantic goal hint: %s", exc)
        _record_timing(timings_ms, "semantic_goal_hint", hint_started)

        vars_started = time.perf_counter()
        response = {
            "narrative": narrative_text,
            "state_changes": state_changes,
            "choices": choices,
            "plausible": bool(final_result.plausible),
            "vars": state_manager.get_contextual_variables(),
        }
        if used_staged_pipeline:
            response["ack_line"] = staged_ack_line
        _record_timing(timings_ms, "build_response", vars_started)

        if triggered_text:
            response["triggered_storylet"] = triggered_text

        persist_idempotent_started = time.perf_counter()
        if idempotency_key and action_event_id is not None:
            try:
                world_memory.persist_action_idempotent_response(
                    db=db,
                    event_id=action_event_id,
                    response_payload=response,
                )
            except Exception as exc:
                logger.warning("Failed to persist idempotent action response: %s", exc)
        _record_timing(
            timings_ms,
            "persist_idempotent_response",
            persist_idempotent_started,
        )

        save_started = time.perf_counter()
        save_state(state_manager, db)
        _record_timing(timings_ms, "save_state", save_started)
        return response

    @staticmethod
    def process_next_turn(
        *,
        db: Session,
        payload: NextReq,
        timings_ms: Dict[str, float] | None = None,
        debug_scores: bool = False,
        ensure_storylets_fn=ensure_storylets,
        pick_storylet_fn=pick_storylet_enhanced,
        adapt_storylet_fn=adapt_storylet_to_context,
        generate_next_beat_fn=generate_next_beat,
        normalize_choice_fn=normalize_choice,
        render_fn=render,
    ) -> Dict[str, Any]:
        """Resolve one /next turn through the shared phase pipeline."""
        from . import world_memory

        state_manager = get_state_manager(payload.session_id, db)

        set_vars_started = time.perf_counter()
        for key, value in (payload.vars or {}).items():
            state_manager.set_variable(key, value)

        if payload.choice_taken:
            intent = ChoiceSelectedIntent(
                label="Player Choice",
                delta=payload.choice_taken,
            )
            reduce_event(db, state_manager, intent)

            tick = SystemTickIntent()
            reduce_event(db, state_manager, tick)
        _record_timing(timings_ms, "set_vars", set_vars_started)

        context_started = time.perf_counter()
        contextual_vars = state_manager.get_contextual_variables()
        _record_timing(timings_ms, "get_contextual_vars", context_started)

        world_bible = state_manager.get_world_bible()
        if settings.enable_jit_beat_generation and world_bible:
            jit_started = time.perf_counter()
            try:
                recent_event_summaries_jit: List[str] = []
                try:
                    recent_events_jit = world_memory.get_world_history(
                        db,
                        session_id=payload.session_id,
                        limit=5,
                    )
                    recent_event_summaries_jit = [str(event.summary).strip() for event in recent_events_jit if str(event.summary).strip()]
                except Exception:
                    pass

                from ..core.scene_card import build_scene_card
                from .spatial_navigator import get_spatial_navigator as get_live_spatial_navigator

                spatial_nav = get_live_spatial_navigator(db)
                scene_card = build_scene_card(state_manager, spatial_nav)

                beat = generate_next_beat_fn(
                    world_bible=world_bible,
                    recent_events=recent_event_summaries_jit,
                    scene_card=scene_card.model_dump(),
                )
                state_manager.advance_story_arc(
                    choices_made=beat.get("choices", []),
                    tension=beat.get("tension"),
                    unresolved_threads=beat.get("unresolved_threads"),
                )
                text = beat["text"]
                choices = [ChoiceOut(**normalize_choice_fn(choice)) for choice in cast(List[Dict[str, Any]], beat.get("choices", []))]
                out = NextResp(text=text, choices=choices, vars=contextual_vars)
                _record_timing(timings_ms, "jit_beat_generation", jit_started)
                save_state(state_manager, db)
                return {"response": out, "debug": None}
            except Exception as exc:
                logger.warning(
                    "JIT beat generation failed (%s) - falling back to storylet path: %s",
                    type(exc).__name__,
                    exc,
                )
                _record_timing(timings_ms, "jit_beat_generation", jit_started)

        ensure_started = time.perf_counter()
        ensure_storylets_fn(db, contextual_vars)
        _record_timing(timings_ms, "ensure_storylets", ensure_started)

        debug_requested = bool(debug_scores and settings.enable_dev_reset)
        selection_debug: Dict[str, Any] | None = {} if debug_requested else None
        select_started = time.perf_counter()
        story = pick_storylet_fn(
            db,
            state_manager,
            debug_selection=selection_debug,
        )
        _record_timing(timings_ms, "pick_storylet", select_started)

        if story is None:
            text = "The tunnel is quiet. Nothing compelling meets the eye."
            choices = [ChoiceOut(label="Wait", set={})]

            if state_manager.environment.danger_level > 3:
                text = "The air feels heavy with danger. Perhaps it is wise to wait and listen."
            elif state_manager.environment.time_of_day == "night":
                text = "The darkness is deep. Something stirs in the shadows, but nothing approaches."
            out = NextResp(text=text, choices=choices, vars=contextual_vars)
        else:
            recent_event_summaries: List[str] = []
            history_started = time.perf_counter()
            try:
                recent_events = world_memory.get_world_history(
                    db,
                    session_id=payload.session_id,
                    limit=3,
                )
                recent_event_summaries = [str(event.summary).strip() for event in recent_events if str(event.summary).strip()]
            except Exception as exc:
                logging.debug(
                    "Could not load recent world history for adaptation: %s",
                    exc,
                )
            finally:
                _record_timing(timings_ms, "load_recent_history", history_started)

            if story.id is None:
                persist_started = time.perf_counter()
                try:
                    db.add(story)
                    db.commit()
                    db.refresh(story)
                except Exception as exc:
                    logger.warning("Failed to persist selected transient stub: %s", exc)
                finally:
                    _record_timing(timings_ms, "persist_stub", persist_started)

            state_manager.advance_story_arc(
                choices_made=payload.vars.get("choices") if payload.vars else [],
            )

            adaptation_context = {
                "variables": contextual_vars,
                "environment": state_manager.environment.__dict__.copy(),
                "recent_events": recent_event_summaries,
                "state_summary": state_manager.get_state_summary(),
            }
            adapt_started = time.perf_counter()
            adapted = adapt_storylet_fn(story, adaptation_context)
            _record_timing(timings_ms, "adapt_storylet", adapt_started)
            text = str(adapted.get("text") or render_fn(cast(str, story.text_template), contextual_vars))
            adapted_choices = adapted.get("choices")
            if not isinstance(adapted_choices, list):
                adapted_choices = cast(List[Dict[str, Any]], story.choices or [])
            choices = [ChoiceOut(**normalize_choice_fn(choice)) for choice in cast(List[Dict[str, Any]], adapted_choices)]
            out = NextResp(text=text, choices=choices, vars=contextual_vars)

            record_started = time.perf_counter()
            try:
                world_memory.record_event(
                    db=db,
                    session_id=payload.session_id,
                    storylet_id=cast(int, story.id),
                    event_type=world_memory.EVENT_TYPE_STORYLET_FIRED,
                    summary=f"Storylet '{story.title}' fired",
                    delta={},
                )
            except Exception as exc:
                logging.warning("Failed to record storylet event: %s", exc)
            finally:
                _record_timing(timings_ms, "record_storylet_event", record_started)

            sim_delta = tick_world_simulation(state_manager)
            if sim_delta.increment or sim_delta.set or sim_delta.append_fact:
                sim_receipt = reduce_event(
                    db,
                    state_manager,
                    SimulationTickIntent(delta=sim_delta),
                )
                try:
                    world_memory.record_event(
                        db=db,
                        session_id=payload.session_id,
                        storylet_id=cast(int, story.id),
                        event_type=world_memory.EVENT_TYPE_SIMULATION_TICK,
                        summary="Deterministic world simulation tick",
                        delta=sim_receipt.applied_changes,
                    )
                except Exception as exc:
                    logging.warning("Failed to record simulation tick: %s", exc)

        save_started = time.perf_counter()
        save_state(state_manager, db)
        _record_timing(timings_ms, "save_state", save_started)
        return {
            "response": out,
            "debug": selection_debug if debug_requested else None,
        }
