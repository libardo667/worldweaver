"""Freeform action endpoint."""

import json
import logging
import re
import time
from typing import Any, Dict

from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...models import Player
from ...services.auth_service import check_pass_not_expired, get_current_player
from ...models.schemas import ActionRequest, ActionResponse
from ...services.game_logic import render
from ...services.llm_client import (
    reset_trace_id,
    run_inference_thread,
    set_trace_id,
)
from ...services import runtime_metrics
from ...services.prefetch_service import schedule_frontier_prefetch
from .orchestration_adapters import run_action_turn_orchestration
from .runtime_helpers import (
    active_trace_id,
    begin_route_runtime,
    finalize_request_metrics,
    record_timing_ms,
    schedule_prefetch_async_best_effort,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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


def _resolve_freeform_action(
    payload: ActionRequest,
    db: Session,
    timings_ms: Dict[str, float] | None = None,
    phase_events: list[tuple[str, Dict[str, Any]]] | None = None,
    ack_line_hint: str | None = None,
) -> Dict[str, Any]:
    """Interpret a freeform action and return canonical ActionResponse payload."""
    return run_action_turn_orchestration(
        db=db,
        payload=payload,
        timings_ms=timings_ms,
        phase_events=phase_events,
        ack_line_hint=ack_line_hint,
        render_fn=render,
    )


@router.post("/action", response_model=ActionResponse)
async def api_freeform_action(
    payload: ActionRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    player: Optional[Player] = Depends(get_current_player),
):
    """Interpret a freeform player action using natural language."""
    if player is not None:
        check_pass_not_expired(player)
    request_runtime = begin_route_runtime(
        route="/api/action",
        response=response,
        request=request,
    )
    trace_id = request_runtime.trace_id
    metrics_route_token = request_runtime.metrics_route_token
    request_started = request_runtime.request_started
    timings_ms = request_runtime.timings_ms
    try:
        resolved = await run_inference_thread(
            _resolve_freeform_action,
            payload,
            db,
            timings_ms,
        )
        await schedule_prefetch_async_best_effort(
            session_id=payload.session_id,
            trigger="api_action",
            bind=db.get_bind(),
            timings_ms=timings_ms,
            logger=logger,
            run_inference_thread_fn=run_inference_thread,
            schedule_prefetch_fn=schedule_frontier_prefetch,
        )
        return resolved
    finally:
        finalize_request_metrics(
            route="/api/action",
            trace_id=trace_id,
            session_id=payload.session_id,
            request_started=request_started,
            timings_ms=timings_ms,
            metrics_route_token=metrics_route_token,
            logger=logger,
        )


@router.post("/action/stream")
async def api_freeform_action_stream(
    payload: ActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    player: Optional[Player] = Depends(get_current_player),
):
    """Stream staged action phases, then emit the final canonical response."""
    if player is not None:
        check_pass_not_expired(player)
    trace_id = active_trace_id(request)
    request_started = time.perf_counter()
    timings_ms: Dict[str, float] = {"staged_pipeline_enabled": 1.0 if settings.enable_staged_action_pipeline else 0.0}

    async def _event_stream():
        stream_started = time.perf_counter()
        trace_token = set_trace_id(trace_id)
        metrics_route_token = runtime_metrics.bind_metrics_route("/api/action/stream")
        stream_status = "ok"
        ack_line = _quick_ack_line(payload.action)
        yield _phase_event("ack", {"ack_line": ack_line})
        record_timing_ms(timings_ms, "stream_ack", stream_started)

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
            record_timing_ms(timings_ms, "resolve_action", resolve_started)
            for phase_name, phase_payload in phase_events:
                yield _phase_event(phase_name, phase_payload)
            yield _sse_event("final", final_payload)
        except Exception as exc:
            stream_status = "error"
            logger.exception("Action streaming failed")
            yield _sse_event("error", {"detail": str(exc)})
        finally:
            await schedule_prefetch_async_best_effort(
                session_id=payload.session_id,
                trigger="api_action_stream",
                bind=db.get_bind(),
                timings_ms=timings_ms,
                logger=logger,
                run_inference_thread_fn=run_inference_thread,
                schedule_prefetch_fn=schedule_frontier_prefetch,
                warning_context="stream",
            )
            record_timing_ms(timings_ms, "stream_total", stream_started)
            finalize_request_metrics(
                route="/api/action/stream",
                trace_id=trace_id,
                session_id=payload.session_id,
                request_started=request_started,
                timings_ms=timings_ms,
                metrics_route_token=metrics_route_token,
                logger=logger,
                status=stream_status,
            )
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
