"""Freeform action endpoint."""

import json
import logging
import re
import sys
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...models.schemas import ActionRequest, ActionResponse
from ...services.llm_client import (
    get_trace_id,
    reset_trace_id,
    run_inference_thread,
    set_trace_id,
)
from ...services.prefetch_service import schedule_frontier_prefetch
from ...services.game_logic import render
from ...services import runtime_metrics
from ...services.session_service import get_spatial_navigator, session_mutation_lock
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


def _phase_event(phase: str, payload: Dict[str, Any]) -> str:
    return _sse_event(f"phase:{phase}", payload)


def _quick_ack_line(action: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(action or "").strip())
    if len(cleaned) > 110:
        cleaned = f"{cleaned[:107]}..."
    return f'You commit to: "{cleaned}".'


def _provisional_action_text(action: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(action or "").strip())
    if len(cleaned) > 180:
        cleaned = f"{cleaned[:177]}..."
    return f'You attempt: "{cleaned}". ' "The world takes a breath as consequences begin to settle..."


def _stream_provisional_chunks(action: str):
    yield _sse_event("draft_chunk", {"text": _provisional_action_text(action)})


def _record_timing(
    timings_ms: Dict[str, float] | None,
    key: str,
    started: float,
) -> None:
    if timings_ms is None:
        return
    timings_ms[key] = round((time.perf_counter() - started) * 1000.0, 3)


def _active_trace_id(request: Request | None = None) -> str:
    if request is not None:
        req_trace = str(getattr(request.state, "trace_id", "")).strip()
        if req_trace:
            return req_trace
    trace_id = str(get_trace_id() or "").strip()
    if trace_id and trace_id != "no-trace":
        return trace_id
    return uuid.uuid4().hex


def _resolve_freeform_action(
    payload: ActionRequest,
    db: Session,
    timings_ms: Dict[str, float] | None = None,
    phase_events: list[tuple[str, Dict[str, Any]]] | None = None,
    ack_line_hint: str | None = None,
) -> Dict[str, Any]:
    """Interpret a freeform action and return canonical ActionResponse payload."""
    from ...services.turn_service import TurnOrchestrator

    with session_mutation_lock(payload.session_id):
        return TurnOrchestrator.process_action_turn(
            db=db,
            payload=payload,
            timings_ms=timings_ms,
            phase_events=phase_events,
            ack_line_hint=ack_line_hint,
            get_spatial_navigator_fn=get_spatial_navigator,
            pick_storylet_fn=pick_storylet_enhanced,
            render_fn=render,
            find_storylet_by_location_fn=find_storylet_by_location,
        )


@router.post("/action", response_model=ActionResponse)
async def api_freeform_action(
    payload: ActionRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Interpret a freeform player action using natural language."""
    trace_id = _active_trace_id(request)
    metrics_route_token = runtime_metrics.bind_metrics_route("/api/action")
    response.headers.setdefault("X-WW-Trace-Id", trace_id)
    request_started = time.perf_counter()
    timings_ms: Dict[str, float] = {}
    try:
        resolved = await run_inference_thread(
            _resolve_freeform_action,
            payload,
            db,
            timings_ms,
        )
        prefetch_started = time.perf_counter()
        try:
            await run_inference_thread(
                schedule_frontier_prefetch,
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
        duration_ms = round((time.perf_counter() - request_started) * 1000.0, 3)
        status = "error" if sys.exc_info()[0] is not None else "ok"
        runtime_metrics.record_route_timing("/api/action", duration_ms, status=status)
        logger.info(
            json.dumps(
                {
                    "event": "request_timing",
                    "route": "/api/action",
                    "trace_id": trace_id,
                    "session_id": payload.session_id,
                    "duration_ms": duration_ms,
                    "timings_ms": timings_ms,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        runtime_metrics.reset_metrics_route(metrics_route_token)


@router.post("/action/stream")
async def api_freeform_action_stream(
    payload: ActionRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Stream staged action phases, then emit the final canonical response."""
    trace_id = _active_trace_id(request)
    request_started = time.perf_counter()
    timings_ms: Dict[str, float] = {"staged_pipeline_enabled": 1.0 if settings.enable_staged_action_pipeline else 0.0}

    async def _event_stream():
        stream_started = time.perf_counter()
        trace_token = set_trace_id(trace_id)
        metrics_route_token = runtime_metrics.bind_metrics_route("/api/action/stream")
        stream_status = "ok"
        ack_line = _quick_ack_line(payload.action)
        yield _phase_event("ack", {"ack_line": ack_line})
        for chunk in _stream_provisional_chunks(payload.action):
            yield chunk
            set_trace_id(trace_id)
        _record_timing(timings_ms, "stream_ack", stream_started)

        try:
            set_trace_id(trace_id)
            resolve_started = time.perf_counter()
            phase_events: list[tuple[str, Dict[str, Any]]] = []
            final_payload = await run_inference_thread(
                _resolve_freeform_action,
                payload,
                db,
                timings_ms,
                phase_events,
                ack_line,
            )
            _record_timing(timings_ms, "resolve_action", resolve_started)
            for phase_name, phase_payload in phase_events:
                yield _phase_event(phase_name, phase_payload)
            yield _sse_event("final", final_payload)
        except Exception as exc:
            stream_status = "error"
            logger.exception("Action streaming failed")
            yield _sse_event("error", {"detail": str(exc)})
        finally:
            prefetch_started = time.perf_counter()
            try:
                await run_inference_thread(
                    schedule_frontier_prefetch,
                    payload.session_id,
                    trigger="api_action_stream",
                    bind=db.get_bind(),
                )
            except Exception as exc:
                logger.debug("Could not schedule frontier prefetch (stream): %s", exc)
            finally:
                _record_timing(timings_ms, "schedule_prefetch", prefetch_started)
            _record_timing(timings_ms, "stream_total", stream_started)
            duration_ms = round((time.perf_counter() - request_started) * 1000.0, 3)
            runtime_metrics.record_route_timing(
                "/api/action/stream",
                duration_ms,
                status=stream_status,
            )
            logger.info(
                json.dumps(
                    {
                        "event": "request_timing",
                        "route": "/api/action/stream",
                        "trace_id": trace_id,
                        "session_id": payload.session_id,
                        "duration_ms": duration_ms,
                        "timings_ms": timings_ms,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
            runtime_metrics.reset_metrics_route(metrics_route_token)
            try:
                reset_trace_id(trace_token)
            except ValueError:
                set_trace_id("")

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-WW-Trace-Id": trace_id,
            "X-Correlation-Id": trace_id,
        },
    )
