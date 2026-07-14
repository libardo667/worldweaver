# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Application service for interpreting and submitting one player action."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import logging
import time
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from ..config import settings
from ..models.schemas import (
    ActionDeltaContract,
    ActionDeltaSetOperation,
    ActionFactAppendOperation,
    ActionRequest,
)
from . import command_interpreter, world_memory
from .action.choices import normalize_action_result_choices
from .action.interpretation import resolve_freeform_action_interpretation
from .action.timing import record_timing
from .event_submission import (
    WorldEventCommand,
    prepare_world_event,
    submit_prepared_world_event,
    submit_world_event,
)
from .llm_client import InferencePolicy, get_trace_id
from .rules.reducer import reduce_event
from .rules.schema import (
    FreeformActionCommittedIntent,
    SimulationTickIntent,
    SystemTickIntent,
)
from .session_service import get_state_manager, save_state, session_mutation_lock
from .simulation.tick import tick_world_simulation

logger = logging.getLogger(__name__)

_BLOCKED_MOVEMENT_KEYS = {"location", "destination", "origin", "in_transit", "sublocation"}
_BLOCKED_MOVEMENT_PREDICATES = {
    "location",
    "is_at",
    "at_location",
    "in_transit",
    "traveled_to",
    "moving_to",
}


def _log_action_event(event: str, **fields: Any) -> None:
    trace_id = get_trace_id()
    payload: Dict[str, Any] = {
        "event": event,
        "trace_id": trace_id,
        "correlation_id": trace_id,
    }
    payload.update(fields)
    logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str))


def _public_contextual_vars(state_manager: Any) -> Dict[str, Any]:
    payload = state_manager.get_contextual_variables()
    if not isinstance(payload, dict):
        return {}
    result = dict(payload)
    result.pop("_scene_card_now", None)
    result.pop("_scene_card_history", None)
    return result


def _build_scene_card_payload(state_manager: Any) -> Dict[str, Any]:
    from ..core.scene_card import build_scene_card

    scene_card = build_scene_card(state_manager).model_dump()
    state_manager.persist_scene_card(scene_card, source="action")
    return scene_card


def _update_motif_ledger(state_manager: Any, narrative_text: str) -> None:
    if not hasattr(state_manager, "extract_motifs_from_text") or not hasattr(state_manager, "append_recent_motifs"):
        return
    extracted = state_manager.extract_motifs_from_text(
        narrative_text,
        max_items=max(1, int(settings.motif_extract_max_per_turn)),
    )
    if extracted:
        state_manager.append_recent_motifs(
            extracted,
            max_items=max(8, int(settings.motif_ledger_max_items)),
        )


def _action_delta_contract(result: Any, choice_vars: Dict[str, Any] | None) -> ActionDeltaContract:
    contract = ActionDeltaContract()
    for key, value in (choice_vars or {}).items():
        contract.set.append(ActionDeltaSetOperation(key=key, value=value))

    state_deltas = result.state_deltas if isinstance(result.state_deltas, dict) else {}
    for key, value in state_deltas.items():
        normalized_key = str(key or "").strip().lower()
        if normalized_key in _BLOCKED_MOVEMENT_KEYS:
            continue
        if any(normalized_key.endswith(f".{suffix}") for suffix in _BLOCKED_MOVEMENT_KEYS):
            continue
        contract.set.append(ActionDeltaSetOperation(key=key, value=value))

    metadata = result.reasoning_metadata if isinstance(result.reasoning_metadata, dict) else {}
    appended_facts = metadata.get("appended_facts")
    if isinstance(appended_facts, list):
        for item in appended_facts[:5]:
            if not isinstance(item, dict):
                continue
            if str(item.get("predicate") or "").strip().lower() in _BLOCKED_MOVEMENT_PREDICATES:
                continue
            try:
                contract.append_fact.append(ActionFactAppendOperation.model_validate(item))
            except Exception:
                continue
    return contract


def _actor_name(state_manager: Any) -> str:
    for key in ("player_role", "player_name", "name"):
        raw_value = str(state_manager.get_variable(key) or "").strip()
        if key == "player_role" and " — " in raw_value:
            raw_value = raw_value.split(" — ", 1)[0].strip()
        if raw_value:
            return raw_value[:120]
    session_id = str(state_manager.effective_world_session_id() or "").strip()
    return session_id[:12] or "Someone"


def _public_summary(result: Any, action_text: str) -> str:
    supplied = str(getattr(result, "public_summary", "") or "").strip()
    if supplied:
        return supplied[:240]
    cleaned = " ".join(str(action_text or "").strip().split()).strip(" \"'").rstrip(".!?")
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
    return (clause[:1].upper() + clause[1:] + ".")[:240]


def _bounded_confidence(value: Any, default: float) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, confidence))


def _filtered_appended_facts(reasoning_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_facts = reasoning_metadata.get("appended_facts")
    if not isinstance(raw_facts, list):
        return []
    return [dict(raw_fact) for raw_fact in raw_facts[:10] if isinstance(raw_fact, dict) and str(raw_fact.get("predicate") or "").strip().lower() not in _BLOCKED_MOVEMENT_PREDICATES]


def _event_payload(
    *,
    base_delta: Dict[str, Any],
    state_manager: Any,
    action_text: str,
    summary: str,
    plausible: bool,
    interpretation_mode: str,
    reasoning_metadata: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    event_delta = dict(base_delta)
    actor = _actor_name(state_manager)
    location = str(event_delta.get("location") or state_manager.get_variable("location") or "").strip()[:120]
    appended_facts = _filtered_appended_facts(reasoning_metadata)

    if plausible and location:
        raw_spatial = event_delta.get("spatial_nodes")
        spatial_nodes = dict(raw_spatial) if isinstance(raw_spatial, dict) else {}
        raw_location = spatial_nodes.get(location)
        location_blob = dict(raw_location) if isinstance(raw_location, dict) else {}
        location_blob.update(
            {
                "last_public_actor": actor,
                "last_public_activity_type": "freeform_action",
                "last_public_activity_summary": summary,
                "last_public_action_text": action_text[:220],
            }
        )
        spatial_nodes[location] = location_blob
        event_delta["spatial_nodes"] = spatial_nodes

    facts: List[Dict[str, Any]] = []
    if appended_facts and location:
        facts.append(
            {
                "subject": actor,
                "subject_type": "entity",
                "predicate": "acted_at",
                "value": location,
                "location": location,
                "summary": summary,
                "confidence": 0.55,
            }
        )
    for raw_fact in appended_facts[:5]:
        subject = str(raw_fact.get("subject") or actor).strip()[:120]
        predicate = str(raw_fact.get("predicate") or "").strip()[:120]
        if not subject or not predicate:
            continue
        fact_location = str(raw_fact.get("location") or location or "").strip()[:120] or None
        facts.append(
            {
                "subject": subject,
                "subject_type": "entity",
                "predicate": predicate,
                "value": raw_fact.get("value"),
                "location": fact_location,
                "summary": summary,
                "confidence": _bounded_confidence(raw_fact.get("confidence"), 0.75),
            }
        )
    if facts:
        event_delta[world_memory.WORLD_FACTS_DELTA_KEY] = {
            "facts": facts,
            "parser_mode": "structured",
        }

    metadata: Dict[str, Any] = {
        "surface": "freeform_action",
        "route": "action",
        "visibility": "public",
        "pipeline": interpretation_mode,
        "plausible": plausible,
        "actor": actor,
    }
    if location:
        metadata["location"] = location
    cleaned_action = str(action_text or "").strip()
    if cleaned_action:
        metadata["action_text"] = cleaned_action[:220]
    return event_delta, metadata


def _action_summary(action_text: str, public_summary: str) -> str:
    cleaned = action_text.rstrip()
    punctuation = "" if cleaned.endswith((".", "!", "?")) else "."
    return f"Player action: {cleaned}{punctuation} Observed: {public_summary}"


def _execute_action(
    *,
    db: Session,
    payload: ActionRequest,
    timings_ms: Dict[str, float] | None,
    phase_events: List[Tuple[str, Dict[str, Any]]] | None,
    ack_line_hint: str | None,
    actor_inference_policy: InferencePolicy | None,
) -> Dict[str, Any]:
    idempotency_key = str(payload.idempotency_key or "").strip()
    started = time.perf_counter()
    if idempotency_key:
        replay = world_memory.get_action_idempotent_response(
            db=db,
            session_id=payload.session_id,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            record_timing(timings_ms, "idempotency_lookup", started)
            return replay
    record_timing(timings_ms, "idempotency_lookup", started)

    state_started = time.perf_counter()
    state_manager = get_state_manager(payload.session_id, db)
    record_timing(timings_ms, "load_state_manager", state_started)

    choice_label = str(payload.choice_label or "").strip()
    choice_intent = str(payload.choice_intent or "").strip() if choice_label else ""
    effective_action = choice_intent or payload.action

    scene_started = time.perf_counter()
    scene_card_now = _build_scene_card_payload(state_manager)
    record_timing(timings_ms, "build_scene_card_now", scene_started)

    interpretation = resolve_freeform_action_interpretation(
        action_text=effective_action,
        state_manager=state_manager,
        world_memory_module=world_memory,
        current_scene=None,
        db=db,
        scene_card_now=scene_card_now,
        timings_ms=timings_ms,
        ack_line_hint=ack_line_hint,
        strict_nonstaged_timing_key="interpret_action_intent",
    )
    result = interpretation.result
    plausible = bool(result.plausible)
    used_staged_pipeline = interpretation.used_staged_pipeline
    ack_line = interpretation.staged_ack_line if (used_staged_pipeline or choice_label) else None

    metadata = result.reasoning_metadata if isinstance(result.reasoning_metadata, dict) else {}
    metadata = dict(metadata)
    applied_deltas: Dict[str, Any] = {}
    prepared_action = None
    event_type = world_memory.EVENT_TYPE_FREEFORM_ACTION

    if plausible:
        delta = _action_delta_contract(result, payload.choice_vars if isinstance(payload.choice_vars, dict) else None)
        prepared_action = prepare_world_event(
            db,
            state_manager,
            FreeformActionCommittedIntent(action_text=payload.action, delta=delta),
        )
        action_receipt = prepared_action.reducer_receipt
        system_tick_receipt = reduce_event(db, state_manager, SystemTickIntent())
        applied_deltas = {
            **action_receipt.applied_changes,
            **system_tick_receipt.applied_changes,
        }
        current_location = state_manager.get_variable("location")
        if current_location:
            applied_deltas["location"] = current_location
        metadata.update(
            {
                "reducer_receipt": action_receipt.model_dump(),
                "system_tick_receipt": system_tick_receipt.model_dump(),
                "scene_card_now": scene_card_now,
            }
        )
        event_type = world_memory.infer_event_type(
            world_memory.EVENT_TYPE_FREEFORM_ACTION,
            applied_deltas,
        )
        _log_action_event(
            "state_committed",
            session_id=payload.session_id,
            action_type="choice" if choice_label else "freeform",
            event_type=event_type,
            applied_change_count=len(applied_deltas),
            state_keys=sorted(applied_deltas.keys())[:20],
        )

    if phase_events is not None:
        phase_events.append(
            (
                "commit",
                {
                    "plausible": plausible,
                    "state_changes": dict(applied_deltas),
                },
            )
        )

    validated_result = replace(result, state_deltas=applied_deltas)
    final_result = validated_result
    if plausible and used_staged_pipeline:
        if phase_events is not None:
            phase_events.append(("narrate", {"status": "started"}))
        narrate_started = time.perf_counter()
        final_result = command_interpreter.render_validated_action_narration(
            action=effective_action,
            ack_line=interpretation.staged_ack_line,
            validated_result=validated_result,
            state_manager=state_manager,
            world_memory_module=world_memory,
            current_scene=None,
            db=db,
            scene_card_now=scene_card_now,
            resolved_movement_target=None,
            inference_policy=actor_inference_policy,
        )
        record_timing(timings_ms, "render_action_narration", narrate_started)

    narrative = str(final_result.narrative_text or "")
    public_summary = _public_summary(final_result, payload.action)
    event_summary = _action_summary(payload.action, public_summary)
    interpretation_mode = "staged" if used_staged_pipeline else "legacy"
    event_delta, event_metadata = _event_payload(
        base_delta=applied_deltas,
        state_manager=state_manager,
        action_text=payload.action,
        summary=event_summary,
        plausible=plausible,
        interpretation_mode=interpretation_mode,
        reasoning_metadata=metadata,
    )
    metadata.update(event_metadata)

    event_started = time.perf_counter()
    command = WorldEventCommand(
        session_id=state_manager.effective_world_session_id(),
        event_type=event_type,
        summary=event_summary,
        delta=event_delta,
        metadata=metadata,
        idempotency_key=idempotency_key or None,
        preserve_event_type=True,
    )
    if prepared_action is not None:
        event_receipt = submit_prepared_world_event(db, command, prepared_action)
    else:
        event_receipt = submit_world_event(db, command)
    action_event_id = int(event_receipt.event.id) if event_receipt.event.id is not None else None
    record_timing(timings_ms, "submit_action_event", event_started)

    if plausible:
        simulation_delta = tick_world_simulation(state_manager)
        if simulation_delta.increment or simulation_delta.set or simulation_delta.append_fact:
            submit_world_event(
                db,
                WorldEventCommand(
                    session_id=state_manager.effective_world_session_id(),
                    event_type=world_memory.EVENT_TYPE_SIMULATION_TICK,
                    summary="Deterministic world simulation tick",
                    intent=SimulationTickIntent(delta=simulation_delta),
                    state_manager=state_manager,
                ),
            )

    current_location = state_manager.get_variable("location") or ""
    if narrative and current_location:
        world_memory.extract_location_mentions(db, narrative, current_location)

    choices = normalize_action_result_choices(final_result.follow_up_choices)
    state_manager.advance_story_arc(choices_made=[choice.model_dump() for choice in choices])
    _update_motif_ledger(state_manager, narrative)

    if choice_intent and used_staged_pipeline:
        pipeline_mode = "unified_intent"
    elif used_staged_pipeline:
        pipeline_mode = "staged_action"
    elif plausible:
        pipeline_mode = "direct_action"
    else:
        pipeline_mode = "action_refusal"
    diagnostics = {
        "action_source": "choice" if choice_label else "freeform",
        "choice_label": choice_label or None,
        "pipeline_mode": pipeline_mode,
        "selection_mode": "action_commit",
        "fallback_reason": "none" if plausible else "action_interpreter_rejected",
        "clarity_level": "committed",
        "scene_clarity_level": "committed",
    }
    response_vars = _public_contextual_vars(state_manager)
    response_vars = {"_ww_diag": diagnostics, **response_vars}
    response: Dict[str, Any] = {
        "narrative": narrative,
        "public_summary": public_summary,
        "state_changes": dict(applied_deltas),
        "choices": [choice.model_dump() for choice in choices],
        "plausible": plausible,
        "vars": response_vars,
        "diagnostics": dict(diagnostics),
    }
    if ack_line is not None:
        response["ack_line"] = ack_line

    save_started = time.perf_counter()
    save_state(state_manager, db)
    record_timing(timings_ms, "save_state", save_started)

    if idempotency_key and action_event_id is not None:
        world_memory.persist_action_idempotent_response(
            db=db,
            event_id=action_event_id,
            response_payload=response,
        )
    return response


def submit_action(
    *,
    db: Session,
    payload: ActionRequest,
    timings_ms: Dict[str, float] | None = None,
    phase_events: List[Tuple[str, Dict[str, Any]]] | None = None,
    ack_line_hint: str | None = None,
    actor_inference_policy: InferencePolicy | None = None,
) -> Dict[str, Any]:
    """Interpret, validate, reduce, and record one action under its session lock."""

    with session_mutation_lock(payload.session_id):
        state_manager = get_state_manager(payload.session_id, db)
        initial_state = deepcopy(state_manager.export_state())
        try:
            return _execute_action(
                db=db,
                payload=payload,
                timings_ms=timings_ms,
                phase_events=phase_events,
                ack_line_hint=ack_line_hint,
                actor_inference_policy=actor_inference_policy,
            )
        except Exception:
            db.rollback()
            state_manager.import_state(initial_state)
            raise
