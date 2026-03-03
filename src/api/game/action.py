"""Freeform action endpoint."""

import json
import logging
import re
import time
import uuid
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Storylet
from ...models.schemas import ActionRequest, ActionResponse
from ...services.game_logic import render
from ...services.llm_client import reset_trace_id, set_trace_id
from ...services.prefetch_service import schedule_frontier_prefetch
from ...services.session_service import get_spatial_navigator, get_state_manager, save_state
from ...services.storylet_selector import pick_storylet_enhanced
from ...services.storylet_utils import find_storylet_by_location

router = APIRouter()
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


def _sse_event(event: str, payload: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _provisional_action_text(action: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(action or "").strip())
    if len(cleaned) > 180:
        cleaned = f"{cleaned[:177]}..."
    return (
        f'You attempt: "{cleaned}". '
        "The world takes a breath as consequences begin to settle..."
    )


def _stream_provisional_chunks(action: str):
    provisional = _provisional_action_text(action)
    words = provisional.split()
    streamed: list[str] = []
    for word in words:
        streamed.append(word)
        yield _sse_event("draft_chunk", {"text": " ".join(streamed)})
        time.sleep(0.012)


def _record_timing(
    timings_ms: Dict[str, float] | None,
    key: str,
    started: float,
) -> None:
    if timings_ms is None:
        return
    timings_ms[key] = round((time.perf_counter() - started) * 1000.0, 3)


def _resolve_freeform_action(
    payload: ActionRequest,
    db: Session,
    timings_ms: Dict[str, float] | None = None,
) -> Dict[str, Any]:
    """Interpret a freeform action and return canonical ActionResponse payload."""
    from ...services import world_memory
    from ...services.command_interpreter import interpret_action

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
    current_storylet = find_storylet_by_location(db, current_location)
    _record_timing(timings_ms, "resolve_current_storylet", location_started)

    interpret_started = time.perf_counter()
    result = interpret_action(
        action=payload.action,
        state_manager=state_manager,
        world_memory_module=world_memory,
        current_storylet=current_storylet,
        db=db,
    )
    _record_timing(timings_ms, "interpret_action", interpret_started)
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

    action_event_id: int | None = None
    record_event_started = time.perf_counter()
    try:
        # If idempotency dedupe skips insert, this returns the existing row.
        event = world_memory.record_event(
            db=db,
            session_id=payload.session_id,
            storylet_id=cast(int, current_storylet.id) if current_storylet else None,
            event_type=event_type,
            summary=f"Player action: {payload.action}. Result: {result.narrative_text[:200]}",
            delta=result.state_deltas,
            state_manager=state_manager,
            metadata=result.reasoning_metadata,
            idempotency_key=idempotency_key or None,
        )
        action_event_id = int(event.id) if event.id is not None else None
    except Exception as exc:
        logger.warning("Failed to record action event: %s", exc)
        if result.state_deltas:
            world_memory.apply_event_delta_to_state(state_manager, result.state_deltas)
    _record_timing(timings_ms, "record_action_event", record_event_started)

    triggered_text = None
    should_trigger = result.should_trigger_storylet or world_memory.should_trigger_storylet(
        event_type,
        result.state_deltas,
    )
    trigger_started = time.perf_counter()
    if should_trigger:
        contextual_vars = state_manager.get_contextual_variables()
        triggered = pick_storylet_enhanced(db, state_manager)
        if triggered:
            triggered_text = render(cast(str, triggered.text_template), contextual_vars)
    _record_timing(timings_ms, "trigger_follow_up_storylet", trigger_started)

    choices_started = time.perf_counter()
    raw_choices = result.follow_up_choices if isinstance(result.follow_up_choices, list) else []
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

    state_changes = result.state_deltas if isinstance(result.state_deltas, dict) else {}
    narrative_text = str(result.narrative_text or "")
    hint_started = time.perf_counter()
    if semantic_goal:
        try:
            from ...services.semantic_selector import compute_player_context_vector

            spatial_nav = get_spatial_navigator(db)
            effective_storylet = current_storylet
            if effective_storylet is None:
                positioned_ids = list(spatial_nav.storylet_positions.keys())
                if positioned_ids:
                    effective_storylet = db.query(Storylet).filter(Storylet.id.in_(positioned_ids)).first()
            if effective_storylet is None:
                raise ValueError("No positioned storylet available for semantic hint")

            context_vector = compute_player_context_vector(state_manager, world_memory, db)
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
        "plausible": bool(result.plausible),
        "vars": state_manager.get_contextual_variables(),
    }
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
    _record_timing(timings_ms, "persist_idempotent_response", persist_idempotent_started)

    save_started = time.perf_counter()
    save_state(state_manager, db)
    _record_timing(timings_ms, "save_state", save_started)

    return response


@router.post("/action", response_model=ActionResponse)
def api_freeform_action(
    payload: ActionRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Interpret a freeform player action using natural language."""
    trace_id = uuid.uuid4().hex
    trace_token = set_trace_id(trace_id)
    response.headers["X-WW-Trace-Id"] = trace_id
    request_started = time.perf_counter()
    timings_ms: Dict[str, float] = {}
    try:
        resolved = _resolve_freeform_action(payload, db, timings_ms=timings_ms)
        prefetch_started = time.perf_counter()
        try:
            schedule_frontier_prefetch(
                payload.session_id,
                trigger="api_action",
                bind=db.get_bind(),
            )
        except Exception as exc:
            logger.debug("Could not schedule frontier prefetch: %s", exc)
        finally:
            timings_ms["schedule_prefetch"] = round((time.perf_counter() - prefetch_started) * 1000.0, 3)
        return resolved
    finally:
        logger.info(
            json.dumps(
                {
                    "event": "request_timing",
                    "route": "/api/action",
                    "trace_id": trace_id,
                    "session_id": payload.session_id,
                    "duration_ms": round((time.perf_counter() - request_started) * 1000.0, 3),
                    "timings_ms": timings_ms,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        reset_trace_id(trace_token)


@router.post("/action/stream")
def api_freeform_action_stream(payload: ActionRequest, db: Session = Depends(get_db)):
    """Stream provisional action narration, then emit the final canonical response."""
    trace_id = uuid.uuid4().hex
    request_started = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    def _event_stream():
        stream_started = time.perf_counter()
        set_trace_id(trace_id)
        for chunk in _stream_provisional_chunks(payload.action):
            yield chunk
            set_trace_id(trace_id)
        _record_timing(timings_ms, "stream_draft_chunks", stream_started)
        try:
            set_trace_id(trace_id)
            resolve_started = time.perf_counter()
            final_payload = _resolve_freeform_action(payload, db, timings_ms=timings_ms)
            _record_timing(timings_ms, "resolve_action", resolve_started)
            yield _sse_event("final", final_payload)
        except Exception as exc:
            logger.exception("Action streaming failed")
            yield _sse_event("error", {"detail": str(exc)})
        finally:
            prefetch_started = time.perf_counter()
            try:
                schedule_frontier_prefetch(
                    payload.session_id,
                    trigger="api_action_stream",
                    bind=db.get_bind(),
                )
            except Exception as exc:
                logger.debug("Could not schedule frontier prefetch (stream): %s", exc)
            finally:
                _record_timing(timings_ms, "schedule_prefetch", prefetch_started)
            _record_timing(timings_ms, "stream_total", stream_started)
            logger.info(
                json.dumps(
                    {
                        "event": "request_timing",
                        "route": "/api/action/stream",
                        "trace_id": trace_id,
                        "session_id": payload.session_id,
                        "duration_ms": round((time.perf_counter() - request_started) * 1000.0, 3),
                        "timings_ms": timings_ms,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
            set_trace_id("")

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-WW-Trace-Id": trace_id,
        },
    )
