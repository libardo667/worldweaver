"""Optional unified turn endpoint."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...models.schemas import (
    ActionRequest,
    ActionResponse,
    NextReq,
    TurnRequest,
    TurnResponse,
)
from ...services.prefetch_service import schedule_frontier_prefetch
from .orchestration_adapters import (
    run_action_turn_orchestration,
    run_next_turn_orchestration,
)
from .runtime_helpers import (
    begin_route_runtime,
    finalize_request_metrics,
    schedule_prefetch_sync_best_effort,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/turn", response_model=TurnResponse)
def api_turn(
    payload: TurnRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Unified turn entrypoint for clients that support the combined contract."""
    if not settings.enable_turn_endpoint:
        raise HTTPException(status_code=404, detail="Not Found")

    request_runtime = begin_route_runtime(
        route="/api/turn",
        response=response,
    )
    trace_id = request_runtime.trace_id
    metrics_route_token = request_runtime.metrics_route_token
    request_started = request_runtime.request_started
    timings_ms = request_runtime.timings_ms

    try:
        if payload.turn_type == "action":
            action_text = str(payload.action or "").strip()
            if not action_text:
                raise HTTPException(
                    status_code=422,
                    detail="action is required when turn_type='action'",
                )

            action_payload = ActionRequest(
                session_id=payload.session_id,
                action=action_text,
                idempotency_key=payload.idempotency_key,
            )
            resolved = run_action_turn_orchestration(
                db=db,
                payload=action_payload,
                timings_ms=timings_ms,
                use_session_lock=True,
            )
            schedule_prefetch_sync_best_effort(
                session_id=payload.session_id,
                trigger="api_turn_action",
                bind=db.get_bind(),
                timings_ms=timings_ms,
                logger=logger,
                schedule_prefetch_fn=schedule_frontier_prefetch,
                warning_context="turn/action",
            )
            return TurnResponse(
                turn_type="action",
                action=ActionResponse(**resolved),
            )

        next_payload = NextReq(
            session_id=payload.session_id,
            vars=payload.vars or {},
            choice_taken=payload.choice_taken,
        )
        result = run_next_turn_orchestration(
            db=db,
            payload=next_payload,
            timings_ms=timings_ms,
            debug_scores=False,
            use_session_lock=True,
        )
        schedule_prefetch_sync_best_effort(
            session_id=payload.session_id,
            trigger="api_turn_next",
            bind=db.get_bind(),
            timings_ms=timings_ms,
            logger=logger,
            schedule_prefetch_fn=schedule_frontier_prefetch,
            warning_context="turn/next",
        )
        return TurnResponse(
            turn_type="next",
            next=result["response"],
        )
    finally:
        finalize_request_metrics(
            route="/api/turn",
            trace_id=trace_id,
            session_id=payload.session_id,
            request_started=request_started,
            timings_ms=timings_ms,
            metrics_route_token=metrics_route_token,
            logger=logger,
        )
