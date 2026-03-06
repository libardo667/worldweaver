"""Story progression endpoints."""

import json
import logging
import time
from typing import Dict, cast

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...models.schemas import NextReq, NextResp
from ...services.game_logic import ensure_storylets, render
from ...services.llm_client import run_inference_thread
from ...services.llm_service import adapt_storylet_to_context, generate_next_beat
from ...services.prefetch_service import schedule_frontier_prefetch
from ...services import runtime_metrics
from ...services.session_service import session_mutation_lock
from ...services.storylet_selector import pick_storylet_enhanced
from ...services.storylet_utils import normalize_choice
from .runtime_helpers import active_trace_id, finalize_request_metrics

router = APIRouter()
logger = logging.getLogger(__name__)


def _resolve_next_turn(
    payload: NextReq,
    debug_scores: bool,
    db: Session,
    timings_ms: Dict[str, float],
):
    from ...services.turn_service import TurnOrchestrator

    with session_mutation_lock(payload.session_id):
        return TurnOrchestrator.process_next_turn(
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


@router.post("/next", response_model=NextResp)
async def api_next(
    payload: NextReq,
    response: Response,
    debug_scores: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Get the next storylet for a session with advanced state management."""
    trace_id = active_trace_id()
    metrics_route_token = runtime_metrics.bind_metrics_route("/api/next")
    response.headers.setdefault("X-WW-Trace-Id", trace_id)
    request_started = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    try:
        result = await run_inference_thread(
            _resolve_next_turn,
            payload,
            debug_scores,
            db,
            timings_ms,
        )

        if debug_scores and settings.enable_dev_reset and result.get("debug") is not None:
            response.headers["X-WorldWeaver-Score-Debug"] = json.dumps(
                result["debug"],
                separators=(",", ":"),
                sort_keys=True,
            )

        prefetch_started = time.perf_counter()
        try:
            await run_inference_thread(
                schedule_frontier_prefetch,
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
        finalize_request_metrics(
            route="/api/next",
            trace_id=trace_id,
            session_id=payload.session_id,
            request_started=request_started,
            timings_ms=timings_ms,
            metrics_route_token=metrics_route_token,
            logger=logger,
        )
