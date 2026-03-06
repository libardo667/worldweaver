"""Shared turn orchestration for /api/next and /api/action."""

from __future__ import annotations

from dataclasses import replace
import json
import logging
import re
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple, cast

from pydantic import TypeAdapter
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import DetachedInstanceError

from ..config import settings
from ..models import Storylet
from ..models.schemas import (
    ActionDeltaContract,
    ActionDeltaIncrementOperation,
    ActionDeltaSetOperation,
    ActionFactAppendOperation,
    ActionRequest,
    ChoiceOut,
    NextReq,
    NextResp,
    StoryletEffectAppendFactOperation,
    StoryletEffectIncrementOperation,
    StoryletEffectOperation,
    StoryletEffectSetOperation,
)
from .game_logic import ensure_storylets, render
from .llm_service import adapt_storylet_to_context, generate_next_beat
from . import prompt_library
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
from .llm_client import get_trace_id

logger = logging.getLogger(__name__)

_SEMANTIC_GOAL_PATTERN = re.compile(
    r"\b(?:looking for|look for|find|search for|seeking|where(?:'s| is))\s+(?:the\s+)?([a-z][a-z0-9 _-]{1,60})",
    re.IGNORECASE,
)
_STORYLET_EFFECT_ADAPTER = TypeAdapter(StoryletEffectOperation)
_STORYLET_EFFECTS_ON_FIRE = "on_fire"
_STORYLET_EFFECTS_ON_CHOICE_COMMIT = "on_choice_commit"
_PENDING_STORYLET_CHOICE_EFFECTS_KEY = "state.pending_storylet_choice_effects"


def _log_structured_turn_event(event: str, **fields: Any) -> None:
    trace_id = get_trace_id()
    payload: Dict[str, Any] = {
        "event": event,
        "trace_id": trace_id,
        "correlation_id": trace_id,
    }
    payload.update(fields)
    logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str))


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


def _safe_storylet_identity(story: Storylet | None) -> tuple[int | None, str | None]:
    """Extract storylet id/title without triggering detached-instance refreshes."""
    if story is None:
        return None, None

    story_id: int | None = None
    story_title: str | None = None

    raw_state = getattr(story, "__dict__", {})
    raw_id = raw_state.get("id")
    if raw_id is not None:
        try:
            story_id = int(raw_id)
        except Exception:
            story_id = None

    if story_id is None:
        try:
            identity = sqlalchemy_inspect(story).identity
            if identity and identity[0] is not None:
                story_id = int(identity[0])
        except Exception:
            story_id = None

    if story_id is None:
        try:
            candidate_id = getattr(story, "id")
            if candidate_id is not None:
                story_id = int(candidate_id)
        except (DetachedInstanceError, Exception):
            story_id = None

    raw_title = raw_state.get("title")
    if raw_title is not None:
        story_title = str(raw_title)
    else:
        try:
            candidate_title = getattr(story, "title")
            if candidate_title is not None:
                story_title = str(candidate_title)
        except (DetachedInstanceError, Exception):
            story_title = None

    return story_id, story_title


def _safe_storylet_field(story: Storylet, field: str, default: Any) -> Any:
    """Read one storylet field without triggering detached-instance failures."""
    raw_state = getattr(story, "__dict__", {})
    if isinstance(raw_state, dict) and field in raw_state:
        value = raw_state.get(field)
    else:
        try:
            value = getattr(story, field)
        except (DetachedInstanceError, Exception):
            return default
    return default if value is None else value


def _snapshot_storylet_payload(story: Storylet) -> Dict[str, Any]:
    """Capture a plain-JSON-safe snapshot so downstream logic never depends on ORM liveness."""
    story_id, story_title = _safe_storylet_identity(story)
    try:
        story_weight = float(_safe_storylet_field(story, "weight", 1.0))
    except (TypeError, ValueError):
        story_weight = 1.0
    requires = _safe_storylet_field(story, "requires", {})
    choices = _safe_storylet_field(story, "choices", [])
    effects = _safe_storylet_field(story, "effects", [])
    return {
        "id": story_id,
        "title": str(story_title or ""),
        "text_template": str(_safe_storylet_field(story, "text_template", "")),
        "requires": (cast(Dict[str, Any], requires) if isinstance(requires, dict) else {}),
        "choices": (cast(List[Dict[str, Any]], choices) if isinstance(choices, list) else []),
        "effects": (cast(List[Dict[str, Any]], effects) if isinstance(effects, list) else []),
        "weight": story_weight,
        "source": str(_safe_storylet_field(story, "source", "authored") or "authored"),
    }


def _inject_next_diagnostics(vars_payload: Dict[str, Any], diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(vars_payload)
    out["_ww_diag"] = dict(diagnostics)
    return out


def _projection_seed_for_storylet(
    session_id: str,
    story_payload: Dict[str, Any],
) -> Dict[str, Any] | None:
    """Resolve one cached non-canon projection stub for narration context."""
    from .prefetch_service import get_cached_frontier

    safe_session_id = str(session_id or "").strip()
    if not safe_session_id:
        return None

    frontier = get_cached_frontier(safe_session_id)
    if not isinstance(frontier, dict):
        return None

    stubs = frontier.get("stubs", [])
    if not isinstance(stubs, list):
        return None

    target_storylet_id = story_payload.get("id")
    target_title = str(story_payload.get("title", "") or "").strip().lower()

    for raw_stub in stubs:
        if not isinstance(raw_stub, dict):
            continue
        stub_storylet_id = raw_stub.get("storylet_id")
        id_match = False
        if target_storylet_id is not None and stub_storylet_id is not None:
            try:
                id_match = int(stub_storylet_id) == int(target_storylet_id)
            except (TypeError, ValueError):
                id_match = False
        title_match = (not id_match) and bool(target_title) and str(raw_stub.get("title", "") or "").strip().lower() == target_title
        if not id_match and not title_match:
            continue

        try:
            normalized_storylet_id = int(stub_storylet_id) if stub_storylet_id is not None else None
        except (TypeError, ValueError):
            normalized_storylet_id = None

        try:
            semantic_score = float(raw_stub.get("semantic_score") or 0.0)
        except (TypeError, ValueError):
            semantic_score = 0.0

        try:
            projection_depth = int(raw_stub.get("projection_depth") or 1)
        except (TypeError, ValueError):
            projection_depth = 1

        result: Dict[str, Any] = {
            "storylet_id": normalized_storylet_id,
            "title": str(raw_stub.get("title", "") or ""),
            "premise": str(raw_stub.get("premise", "") or ""),
            "location": str(raw_stub.get("location", "") or ""),
            "semantic_score": semantic_score,
            "projection_depth": max(1, projection_depth),
            "non_canon": bool(raw_stub.get("non_canon", True)),
            "source": str(raw_stub.get("source", "prefetch_projection") or "prefetch_projection"),
            "expires_in_seconds": max(0, int(frontier.get("expires_in_seconds", 0) or 0)),
        }
        # Attach BFS projection tree metadata when available
        projection_tree = frontier.get("projection_tree")
        if isinstance(projection_tree, dict):
            result["projection_tree_depth"] = int(projection_tree.get("max_depth_reached", 0))
            result["projection_tree_node_count"] = int(projection_tree.get("total_nodes", 0))
            result["projection_tree_referee_scored"] = bool(projection_tree.get("referee_scored", False))
        return result
    return None


def _storylet_effects_to_delta_contract(
    raw_effects: Any,
    *,
    trigger: str,
) -> tuple[ActionDeltaContract, List[Dict[str, Any]]]:
    contract = ActionDeltaContract()
    normalized: List[Dict[str, Any]] = []
    if not isinstance(raw_effects, list):
        return contract, normalized

    for raw in raw_effects[:20]:
        if not isinstance(raw, dict):
            continue
        try:
            parsed = _STORYLET_EFFECT_ADAPTER.validate_python(raw)
        except Exception:
            continue
        if str(getattr(parsed, "when", _STORYLET_EFFECTS_ON_FIRE)) != trigger:
            continue

        if isinstance(parsed, StoryletEffectSetOperation):
            contract.set.append(
                ActionDeltaSetOperation(
                    key=parsed.key,
                    value=parsed.value,
                )
            )
        elif isinstance(parsed, StoryletEffectIncrementOperation):
            contract.increment.append(
                ActionDeltaIncrementOperation(
                    key=parsed.key,
                    amount=float(parsed.amount),
                )
            )
        elif isinstance(parsed, StoryletEffectAppendFactOperation):
            contract.append_fact.append(
                ActionFactAppendOperation(
                    subject=parsed.subject,
                    predicate=parsed.predicate,
                    value=parsed.value,
                    location=parsed.location,
                    confidence=float(parsed.confidence),
                )
            )
        else:
            continue

        normalized.append(parsed.model_dump())

    return contract, normalized


def _public_contextual_vars(state_manager: Any) -> Dict[str, Any]:
    payload = state_manager.get_contextual_variables()
    if not isinstance(payload, dict):
        return {}
    out = dict(payload)
    out.pop("_scene_card_now", None)
    out.pop("_scene_card_history", None)
    return out


def _build_scene_card_payload(
    *,
    db: Session,
    state_manager: Any,
    get_spatial_navigator_fn=get_spatial_navigator,
) -> Dict[str, Any]:
    from ..core.scene_card import build_scene_card

    spatial_nav = get_spatial_navigator_fn(db)
    if not hasattr(spatial_nav, "storylet_positions"):
        spatial_nav = SimpleNamespace(storylet_positions={})
    scene_card = build_scene_card(state_manager, spatial_nav).model_dump()
    state_manager.persist_scene_card(scene_card, source="turn")
    return scene_card


def _update_motif_ledger_from_narrative(
    *,
    state_manager: Any,
    narrative_text: str,
) -> List[str]:
    """Extract motifs from committed narration and append to bounded ledger."""
    if not hasattr(state_manager, "extract_motifs_from_text"):
        return []
    if not hasattr(state_manager, "append_recent_motifs"):
        return []
    extracted = state_manager.extract_motifs_from_text(
        narrative_text,
        max_items=max(1, int(settings.motif_extract_max_per_turn)),
    )
    if not extracted:
        return []
    return list(
        state_manager.append_recent_motifs(
            extracted,
            max_items=max(8, int(settings.motif_ledger_max_items)),
        )
    )


def _action_result_to_delta_contract(
    result: Any,
) -> ActionDeltaContract:
    from ..models.schemas import ActionFactAppendOperation

    contract = ActionDeltaContract()
    state_deltas = result.state_deltas if isinstance(result.state_deltas, dict) else {}
    for key, value in state_deltas.items():
        contract.set.append(ActionDeltaSetOperation(key=key, value=value))

    metadata = result.reasoning_metadata if isinstance(result.reasoning_metadata, dict) else {}
    appended_facts = metadata.get("appended_facts")
    if isinstance(appended_facts, list):
        for item in appended_facts[:5]:
            if not isinstance(item, dict):
                continue
            try:
                contract.append_fact.append(ActionFactAppendOperation.model_validate(item))
            except Exception:
                continue
    return contract


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
        current_storylet_id, _ = _safe_storylet_identity(current_storylet)
        _record_timing(timings_ms, "resolve_current_storylet", location_started)
        scene_card_started = time.perf_counter()
        scene_card_now = _build_scene_card_payload(
            db=db,
            state_manager=state_manager,
            get_spatial_navigator_fn=get_spatial_navigator_fn,
        )
        _record_timing(timings_ms, "build_scene_card_now", scene_card_started)

        staged_ack_line = ack_line_hint or _quick_ack_line(payload.action)
        strict_three_layer = bool(settings.enable_strict_three_layer_architecture)
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
                scene_card_now=scene_card_now,
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
                if strict_three_layer:
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
                        action=payload.action,
                        state_manager=state_manager,
                        world_memory_module=world_memory,
                        current_storylet=current_storylet,
                        db=db,
                        scene_card_now=scene_card_now,
                    )
                    _record_timing(
                        timings_ms,
                        "interpret_action_fallback",
                        fallback_started,
                    )
        else:
            interpret_started = time.perf_counter()
            if strict_three_layer:
                staged_intent = command_interpreter.interpret_action_intent(
                    action=payload.action,
                    state_manager=state_manager,
                    world_memory_module=world_memory,
                    current_storylet=current_storylet,
                    db=db,
                    scene_card_now=scene_card_now,
                )
                if staged_intent is not None:
                    staged_intent = action_validation_policy.validate_action_intent(
                        intent=staged_intent,
                        action_text=payload.action,
                        state_manager=state_manager,
                        world_memory_module=world_memory,
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
            else:
                result = command_interpreter.interpret_action(
                    action=payload.action,
                    state_manager=state_manager,
                    world_memory_module=world_memory,
                    current_storylet=current_storylet,
                    db=db,
                    scene_card_now=scene_card_now,
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

        applied_deltas: Dict[str, Any] = {}
        committed_deltas: Dict[str, Any] = {}
        reducer_receipt_payload: Dict[str, Any] = {}
        tick_receipt_payload: Dict[str, Any] = {}
        event_type = world_memory.EVENT_TYPE_FREEFORM_ACTION
        action_event_id: int | None = None
        record_event_started = time.perf_counter()
        try:
            delta_contract = _action_result_to_delta_contract(result)
            intent = FreeformActionCommittedIntent(
                action_text=payload.action,
                delta=delta_contract,
            )
            receipt = reduce_event(db, state_manager, intent)
            tick_receipt = reduce_event(db, state_manager, SystemTickIntent())
            committed_deltas = dict(receipt.applied_changes)
            applied_deltas = {**committed_deltas, **tick_receipt.applied_changes}
            reducer_receipt_payload = receipt.model_dump()
            tick_receipt_payload = tick_receipt.model_dump()
            event_type = world_memory.infer_event_type(
                world_memory.EVENT_TYPE_FREEFORM_ACTION,
                applied_deltas,
            )

            metadata = result.reasoning_metadata if isinstance(result.reasoning_metadata, dict) else {}
            metadata = dict(metadata)
            metadata["reducer_receipt"] = reducer_receipt_payload
            metadata["system_tick_receipt"] = tick_receipt_payload
            metadata["scene_card_now"] = scene_card_now
            _log_structured_turn_event(
                "state_committed",
                session_id=payload.session_id,
                turn_type="action",
                event_type=event_type,
                applied_change_count=len(applied_deltas),
                state_keys=sorted(list(applied_deltas.keys()))[:20],
            )

            event = world_memory.record_event(
                db=db,
                session_id=payload.session_id,
                storylet_id=current_storylet_id,
                event_type=event_type,
                summary=f"Player action: {payload.action}. Result: {result.narrative_text[:200]}",
                delta=applied_deltas,
                state_manager=None,
                metadata=metadata,
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
                    storylet_id=current_storylet_id,
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
            applied_deltas,
        )
        trigger_started = time.perf_counter()
        if should_trigger:
            contextual_vars = state_manager.get_contextual_variables()
            triggered = pick_storylet_fn(db, state_manager)
            if triggered:
                triggered_text = render_fn(cast(str, triggered.text_template), contextual_vars)
        _record_timing(timings_ms, "trigger_follow_up_storylet", trigger_started)

        validated_result = result
        if applied_deltas:
            validated_result = replace(validated_result, state_deltas=applied_deltas)
        if reducer_receipt_payload or tick_receipt_payload:
            metadata = validated_result.reasoning_metadata if isinstance(validated_result.reasoning_metadata, dict) else {}
            metadata = dict(metadata)
            if reducer_receipt_payload:
                metadata["reducer_receipt"] = reducer_receipt_payload
            if tick_receipt_payload:
                metadata["system_tick_receipt"] = tick_receipt_payload
            metadata["scene_card_now"] = scene_card_now
            validated_result = replace(validated_result, reasoning_metadata=metadata)
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
                scene_card_now=scene_card_now,
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

        state_changes = dict(applied_deltas)
        narrative_text = str(final_result.narrative_text or "")
        hint_started = time.perf_counter()
        if semantic_goal and settings.enable_v3_player_hint_channel:
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
                effective_storylet_id, _ = _safe_storylet_identity(effective_storylet)
                if effective_storylet_id is None:
                    raise ValueError("No stable storylet id available for semantic hint")

                context_vector = compute_player_context_vector(
                    state_manager,
                    world_memory,
                    db,
                )
                goal_hint = spatial_nav.get_semantic_goal_hint(
                    current_storylet_id=effective_storylet_id,
                    player_vars=_public_contextual_vars(state_manager),
                    semantic_goal=semantic_goal,
                    context_vector=context_vector,
                )
                if goal_hint and goal_hint.get("hint"):
                    narrative_text = f"{narrative_text} {goal_hint['hint']}".strip()
            except Exception as exc:
                logger.debug("Could not resolve semantic goal hint: %s", exc)
        _record_timing(timings_ms, "semantic_goal_hint", hint_started)
        motif_started = time.perf_counter()
        _update_motif_ledger_from_narrative(
            state_manager=state_manager,
            narrative_text=narrative_text,
        )
        _record_timing(timings_ms, "update_motif_ledger", motif_started)

        vars_started = time.perf_counter()
        response = {
            "narrative": narrative_text,
            "state_changes": state_changes,
            "choices": choices,
            "plausible": bool(final_result.plausible),
            "vars": _public_contextual_vars(state_manager),
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
        pre_storylet_applied: Dict[str, Any] = {}
        choice_effect_receipt_payload: Dict[str, Any] = {}
        choice_effect_ops_applied: List[Dict[str, Any]] = []

        set_vars_started = time.perf_counter()
        inbound_vars = payload.vars if isinstance(payload.vars, dict) else {}
        if inbound_vars:
            var_delta = ActionDeltaContract()
            for key, value in inbound_vars.items():
                var_delta.set.append(ActionDeltaSetOperation(key=key, value=value))
            var_receipt = reduce_event(
                db,
                state_manager,
                ChoiceSelectedIntent(
                    label="Client Vars Sync",
                    delta=var_delta,
                ),
            )
            pre_storylet_applied.update(var_receipt.applied_changes)

        if payload.choice_taken:
            intent = ChoiceSelectedIntent(
                label="Player Choice",
                delta=payload.choice_taken,
            )
            choice_receipt = reduce_event(db, state_manager, intent)
            pre_storylet_applied.update(choice_receipt.applied_changes)

            choice_effects_started = time.perf_counter()
            pending_choice_effects = state_manager.get_variable(
                _PENDING_STORYLET_CHOICE_EFFECTS_KEY,
                None,
            )
            pending_effects_payload: Any = None
            if isinstance(pending_choice_effects, dict):
                pending_effects_payload = pending_choice_effects.get("effects", [])

            pending_delta, choice_effect_ops_applied = _storylet_effects_to_delta_contract(
                pending_effects_payload,
                trigger=_STORYLET_EFFECTS_ON_CHOICE_COMMIT,
            )
            if choice_effect_ops_applied:
                pending_receipt = reduce_event(
                    db,
                    state_manager,
                    ChoiceSelectedIntent(
                        label="Storylet Choice Commit Effects",
                        delta=pending_delta,
                    ),
                )
                pre_storylet_applied.update(pending_receipt.applied_changes)
                choice_effect_receipt_payload = pending_receipt.model_dump()
            state_manager.delete_variable(_PENDING_STORYLET_CHOICE_EFFECTS_KEY)
            _record_timing(
                timings_ms,
                "apply_storylet_choice_effects",
                choice_effects_started,
            )

            tick = SystemTickIntent()
            tick_receipt = reduce_event(db, state_manager, tick)
            pre_storylet_applied.update(tick_receipt.applied_changes)
        if pre_storylet_applied:
            _log_structured_turn_event(
                "state_committed",
                session_id=payload.session_id,
                turn_type="next",
                event_type="choice_or_vars",
                applied_change_count=len(pre_storylet_applied),
                state_keys=sorted(list(pre_storylet_applied.keys()))[:20],
            )
        _record_timing(timings_ms, "set_vars", set_vars_started)
        goal_backfill_started = time.perf_counter()
        goal_backfill = state_manager.backfill_primary_goal_if_empty_after_initial_turn(
            minimum_turn_count=1,
        )
        if bool(goal_backfill.get("applied")):
            _log_structured_turn_event(
                "goal_backfilled",
                session_id=payload.session_id,
                turn_type="next",
                primary_goal=goal_backfill.get("primary_goal", ""),
                source=goal_backfill.get("source", ""),
                turn_count=goal_backfill.get("turn_count", 0),
            )
        _record_timing(timings_ms, "backfill_primary_goal", goal_backfill_started)

        context_started = time.perf_counter()
        contextual_vars = _public_contextual_vars(state_manager)
        _record_timing(timings_ms, "get_contextual_vars", context_started)
        scene_card_started = time.perf_counter()
        scene_card_now = _build_scene_card_payload(
            db=db,
            state_manager=state_manager,
            get_spatial_navigator_fn=get_spatial_navigator,
        )
        motifs_recent = list(state_manager.get_recent_motifs(limit=max(8, int(settings.motif_ledger_max_items))))
        sensory_palette = prompt_library.build_scene_card_sensory_palette(scene_card_now)
        _record_timing(timings_ms, "build_scene_card_now", scene_card_started)

        world_bible = state_manager.get_world_bible()
        projection_seeded_narration_enabled = bool(settings.enable_v3_projection_seeded_narration)
        player_hint_channel_enabled = bool(settings.enable_v3_player_hint_channel)
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

                beat = generate_next_beat_fn(
                    world_bible=world_bible,
                    recent_events=recent_event_summaries_jit,
                    scene_card=scene_card_now,
                    motifs_recent=motifs_recent,
                    sensory_palette=sensory_palette,
                )
                state_manager.advance_story_arc(
                    choices_made=beat.get("choices", []),
                    tension=beat.get("tension"),
                    unresolved_threads=beat.get("unresolved_threads"),
                )
                text = beat["text"]
                _update_motif_ledger_from_narrative(
                    state_manager=state_manager,
                    narrative_text=text,
                )
                choices = [ChoiceOut(**normalize_choice_fn(choice)) for choice in cast(List[Dict[str, Any]], beat.get("choices", []))]
                out = NextResp(
                    text=text,
                    choices=choices,
                    vars=_inject_next_diagnostics(
                        contextual_vars,
                        {
                            "selection_mode": "jit_beat_generation",
                            "active_storylets_count": 0,
                            "eligible_storylets_count": 0,
                            "fallback_reason": "none",
                            "narrative_source": "jit_beat",
                            "projection_seeded_narration_enabled": projection_seeded_narration_enabled,
                            "projection_seed_used": False,
                            "player_hint_channel_enabled": player_hint_channel_enabled,
                        },
                    ),
                )
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
        selection_debug: Dict[str, Any] = {}
        select_started = time.perf_counter()
        story = pick_storylet_fn(
            db,
            state_manager,
            debug_selection=selection_debug,
        )
        story_id, story_title = _safe_storylet_identity(story)
        selection_mode = None
        selection_mode = selection_debug.get("selection_mode")
        _log_structured_turn_event(
            "storylet_selected",
            session_id=payload.session_id,
            turn_type="next",
            storylet_id=story_id,
            storylet_title=story_title,
            selection_mode=str(selection_mode or "none"),
        )
        _record_timing(timings_ms, "pick_storylet", select_started)

        fallback_reason = "none"
        narrative_source = "storylet_selection"

        if story is None:
            eligible_count = int(selection_debug.get("eligible_count", 0) or 0)
            fallback_reason = "no_eligible_storylets" if eligible_count <= 0 else "no_storylet_selected"
            narrative_source = "engine_idle_fallback"
            text = "The tunnel is quiet. Nothing compelling meets the eye."
            choices = [ChoiceOut(label="Wait", set={})]

            if state_manager.environment.danger_level > 3:
                text = "The air feels heavy with danger. Perhaps it is wise to wait and listen."
            elif state_manager.environment.time_of_day == "night":
                text = "The darkness is deep. Something stirs in the shadows, but nothing approaches."
            _update_motif_ledger_from_narrative(
                state_manager=state_manager,
                narrative_text=text,
            )
            out = NextResp(
                text=text,
                choices=choices,
                vars=_inject_next_diagnostics(
                    contextual_vars,
                    {
                        "selection_mode": str(selection_mode or "none"),
                        "active_storylets_count": int(selection_debug.get("active_storylets_count", 0) or 0),
                        "eligible_storylets_count": int(selection_debug.get("eligible_count", 0) or 0),
                        "fallback_reason": fallback_reason,
                        "narrative_source": narrative_source,
                        "projection_seeded_narration_enabled": projection_seeded_narration_enabled,
                        "projection_seed_used": False,
                        "player_hint_channel_enabled": player_hint_channel_enabled,
                    },
                ),
            )
        else:
            story_payload = _snapshot_storylet_payload(story)
            story_id = cast(int | None, story_payload.get("id"))
            story_title = str(story_payload.get("title") or "")
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

            if story_id is None:
                persist_started = time.perf_counter()
                try:
                    db.add(story)
                    db.commit()
                    db.refresh(story)
                    story_payload = _snapshot_storylet_payload(story)
                    story_id = cast(int | None, story_payload.get("id"))
                    story_title = str(story_payload.get("title") or "")
                except Exception as exc:
                    db.rollback()
                    logger.warning("Failed to persist selected transient stub: %s", exc)
                finally:
                    _record_timing(timings_ms, "persist_stub", persist_started)

            state_manager.advance_story_arc(
                choices_made=payload.vars.get("choices") if payload.vars else [],
            )

            selected_projection_stub: Dict[str, Any] | None = None
            if projection_seeded_narration_enabled:
                selected_projection_stub = _projection_seed_for_storylet(
                    payload.session_id,
                    story_payload,
                )

            adaptation_context = {
                "variables": contextual_vars,
                "environment": state_manager.environment.__dict__.copy(),
                "recent_events": recent_event_summaries,
                "state_summary": state_manager.get_state_summary(),
                "scene_card_now": scene_card_now,
                "goal_lens": state_manager.get_goal_lens_payload(),
                "motifs_recent": motifs_recent,
                "sensory_palette": sensory_palette,
            }
            if selected_projection_stub is not None:
                adaptation_context["selected_projection_stub"] = selected_projection_stub
            adapt_started = time.perf_counter()
            adapted = adapt_storylet_fn(SimpleNamespace(**story_payload), adaptation_context)
            _record_timing(timings_ms, "adapt_storylet", adapt_started)
            text = str(adapted.get("text") or render_fn(str(story_payload.get("text_template", "")), contextual_vars))
            _update_motif_ledger_from_narrative(
                state_manager=state_manager,
                narrative_text=text,
            )
            adapted_choices = adapted.get("choices")
            if not isinstance(adapted_choices, list):
                adapted_choices = cast(List[Dict[str, Any]], story_payload.get("choices", []))
            if not str(adapted.get("text") or "").strip():
                fallback_reason = "template_fallback_after_adaptation"
                narrative_source = "template_fallback"
            else:
                narrative_source = f"storylet_{str(story_payload.get('source', 'authored') or 'authored')}"
            choices = [ChoiceOut(**normalize_choice_fn(choice)) for choice in cast(List[Dict[str, Any]], adapted_choices)]

            fire_effects_started = time.perf_counter()
            storylet_effect_delta, fire_effect_ops_applied = _storylet_effects_to_delta_contract(
                story_payload.get("effects", []),
                trigger=_STORYLET_EFFECTS_ON_FIRE,
            )
            storylet_effect_applied_changes: Dict[str, Any] = {}
            storylet_effect_receipt_payload: Dict[str, Any] = {}
            if fire_effect_ops_applied:
                fire_receipt = reduce_event(
                    db,
                    state_manager,
                    ChoiceSelectedIntent(
                        label="Storylet Fire Effects",
                        delta=storylet_effect_delta,
                    ),
                )
                storylet_effect_applied_changes.update(fire_receipt.applied_changes)
                storylet_effect_receipt_payload = fire_receipt.model_dump()

            _, pending_choice_effect_ops = _storylet_effects_to_delta_contract(
                story_payload.get("effects", []),
                trigger=_STORYLET_EFFECTS_ON_CHOICE_COMMIT,
            )
            if pending_choice_effect_ops:
                state_manager.set_variable(
                    _PENDING_STORYLET_CHOICE_EFFECTS_KEY,
                    {
                        "storylet_id": story_id,
                        "storylet_title": (story_title or "unknown"),
                        "effects": pending_choice_effect_ops,
                    },
                )
            else:
                state_manager.delete_variable(_PENDING_STORYLET_CHOICE_EFFECTS_KEY)
            _record_timing(timings_ms, "apply_storylet_fire_effects", fire_effects_started)

            final_contextual_vars = _public_contextual_vars(state_manager)
            out = NextResp(
                text=text,
                choices=choices,
                vars=_inject_next_diagnostics(
                    final_contextual_vars,
                    {
                        "selection_mode": str(selection_mode or "none"),
                        "active_storylets_count": int(selection_debug.get("active_storylets_count", 0) or 0),
                        "eligible_storylets_count": int(selection_debug.get("eligible_count", 0) or 0),
                        "fallback_reason": fallback_reason,
                        "narrative_source": narrative_source,
                        "projection_seeded_narration_enabled": projection_seeded_narration_enabled,
                        "projection_seed_used": bool(selected_projection_stub),
                        "projection_seed_storylet_id": (selected_projection_stub.get("storylet_id") if selected_projection_stub is not None else None),
                        "player_hint_channel_enabled": player_hint_channel_enabled,
                    },
                ),
            )

            record_started = time.perf_counter()
            try:
                event_metadata: Dict[str, Any] = {}
                if fire_effect_ops_applied:
                    event_metadata = {
                        world_memory.STORYLET_EFFECTS_TRIGGER_KEY: _STORYLET_EFFECTS_ON_FIRE,
                        world_memory.STORYLET_EFFECTS_METADATA_KEY: fire_effect_ops_applied,
                        world_memory.STORYLET_EFFECTS_RECEIPT_KEY: storylet_effect_receipt_payload,
                    }
                if choice_effect_ops_applied:
                    event_metadata[world_memory.STORYLET_CHOICE_COMMIT_EFFECTS_KEY] = {
                        world_memory.STORYLET_EFFECTS_TRIGGER_KEY: _STORYLET_EFFECTS_ON_CHOICE_COMMIT,
                        world_memory.STORYLET_EFFECTS_METADATA_KEY: choice_effect_ops_applied,
                        world_memory.STORYLET_EFFECTS_RECEIPT_KEY: choice_effect_receipt_payload,
                    }
                world_memory.record_event(
                    db=db,
                    session_id=payload.session_id,
                    storylet_id=story_id,
                    event_type=world_memory.EVENT_TYPE_STORYLET_FIRED,
                    summary=f"Storylet '{story_title or 'unknown'}' fired",
                    delta=storylet_effect_applied_changes,
                    metadata=event_metadata or None,
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
                        storylet_id=story_id,
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
