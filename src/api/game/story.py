"""Story progression endpoints."""

import json
import logging
import sys
import time
import uuid
from typing import Dict, cast

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...models.schemas import NextReq, NextResp
from ...services.game_logic import ensure_storylets, render
from ...services.llm_client import reset_trace_id, set_trace_id
from ...services.llm_service import adapt_storylet_to_context, generate_next_beat
from ...services.prefetch_service import schedule_frontier_prefetch
from ...services import runtime_metrics
from ...services.session_service import session_mutation_lock
from ...services.storylet_selector import pick_storylet_enhanced
from ...services.storylet_utils import normalize_choice

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/next", response_model=NextResp)
def api_next(
    payload: NextReq,
    response: Response,
    debug_scores: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Get the next storylet for a session with advanced state management."""
    from ...services.turn_service import TurnOrchestrator

    trace_id = uuid.uuid4().hex
    trace_token = set_trace_id(trace_id)
    metrics_route_token = runtime_metrics.bind_metrics_route("/api/next")
    response.headers["X-WW-Trace-Id"] = trace_id
    request_started = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    try:
        with session_mutation_lock(payload.session_id):
            result = TurnOrchestrator.process_next_turn(
                db=db,
                payload=payload,
                timings_ms=timings_ms,
                debug_scores=debug_scores,
                ensure_storylets_fn=ensure_storylets,
                pick_storylet_fn=pick_storylet_enhanced,
                adapt_storylet_fn=adapt_storylet_to_context,
                generate_next_beat_fn=generate_next_beat,
                normalize_choice_fn=normalize_choice,
                render_fn=render,
            )

        if debug_scores and settings.enable_dev_reset and result.get("debug") is not None:
            response.headers["X-WorldWeaver-Score-Debug"] = json.dumps(
                result["debug"],
                separators=(",", ":"),
                sort_keys=True,
            )

        prefetch_started = time.perf_counter()
        try:
            schedule_frontier_prefetch(
                payload.session_id,
                trigger="api_next",
                bind=db.get_bind(),
            )
        except Exception as exc:
            logger.debug("Could not schedule frontier prefetch: %s", exc)
        finally:
            timings_ms["schedule_prefetch"] = round(
                (time.perf_counter() - prefetch_started) * 1000.0,
                3,
            )

        return cast(NextResp, result["response"])
    finally:
        duration_ms = round((time.perf_counter() - request_started) * 1000.0, 3)
        status = "error" if sys.exc_info()[0] is not None else "ok"
        runtime_metrics.record_route_timing("/api/next", duration_ms, status=status)
        logger.info(
            json.dumps(
                {
                    "event": "request_timing",
                    "route": "/api/next",
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
        reset_trace_id(trace_token)
