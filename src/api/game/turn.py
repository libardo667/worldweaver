"""Optional unified turn endpoint."""

import logging
import time
from typing import Dict

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
from ...services import runtime_metrics
from ...services.game_logic import ensure_storylets, render
from ...services.llm_service import adapt_storylet_to_context, generate_next_beat
from ...services.prefetch_service import schedule_frontier_prefetch
from ...services.session_service import get_spatial_navigator, session_mutation_lock
from ...services.storylet_selector import pick_storylet_enhanced
from ...services.storylet_utils import find_storylet_by_location, normalize_choice
from ...services.turn_service import TurnOrchestrator
from .runtime_helpers import active_trace_id, finalize_request_metrics

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

    trace_id = active_trace_id()
    metrics_route_token = runtime_metrics.bind_metrics_route("/api/turn")
    response.headers.setdefault("X-WW-Trace-Id", trace_id)
    request_started = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    try:
        with session_mutation_lock(payload.session_id):
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
                resolved = TurnOrchestrator.process_action_turn(
                    db=db,
                    payload=action_payload,
                    timings_ms=timings_ms,
                    get_spatial_navigator_fn=get_spatial_navigator,
                    pick_storylet_fn=pick_storylet_enhanced,
                    render_fn=render,
                    find_storylet_by_location_fn=find_storylet_by_location,
                )
                prefetch_started = time.perf_counter()
                try:
                    schedule_frontier_prefetch(
                        payload.session_id,
                        trigger="api_turn_action",
                        bind=db.get_bind(),
                    )
                except Exception as exc:
                    logger.debug("Could not schedule frontier prefetch (turn/action): %s", exc)
                finally:
                    timings_ms["schedule_prefetch"] = round(
                        (time.perf_counter() - prefetch_started) * 1000.0,
                        3,
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
            result = TurnOrchestrator.process_next_turn(
                db=db,
                payload=next_payload,
                timings_ms=timings_ms,
                debug_scores=False,
                ensure_storylets_fn=ensure_storylets,
                pick_storylet_fn=pick_storylet_enhanced,
                adapt_storylet_fn=adapt_storylet_to_context,
                generate_next_beat_fn=generate_next_beat,
                normalize_choice_fn=normalize_choice,
                render_fn=render,
            )
            prefetch_started = time.perf_counter()
            try:
                schedule_frontier_prefetch(
                    payload.session_id,
                    trigger="api_turn_next",
                    bind=db.get_bind(),
                )
            except Exception as exc:
                logger.debug("Could not schedule frontier prefetch (turn/next): %s", exc)
            finally:
                timings_ms["schedule_prefetch"] = round(
                    (time.perf_counter() - prefetch_started) * 1000.0,
                    3,
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
