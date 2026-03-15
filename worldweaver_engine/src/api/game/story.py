"""Story progression endpoints."""

import json
import logging
from typing import Dict, cast

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...models import Player
from ...models.schemas import NextReq, NextResp
from ...services.auth_service import get_current_player
from ...services.game_logic import ensure_storylets, render
from ...services.llm_client import run_inference_thread
from ...services.llm_service import adapt_storylet_to_context, generate_next_beat
from ...services.prefetch_service import schedule_frontier_prefetch
from ...services.player_api_keys import bind_request_api_key, reset_bound_request_api_key
from ...services.storylet_selector import pick_storylet_enhanced
from ...services.storylet_utils import normalize_choice
from .orchestration_adapters import run_next_turn_orchestration
from .runtime_helpers import (
    begin_route_runtime,
    finalize_request_metrics,
    schedule_prefetch_async_best_effort,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _resolve_next_turn(
    payload: NextReq,
    debug_scores: bool,
    db: Session,
    timings_ms: Dict[str, float],
):
    return run_next_turn_orchestration(
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
    player: Player | None = Depends(get_current_player),
):
    """Get the next storylet for a session with advanced state management."""
    request_runtime = begin_route_runtime(
        route="/api/next",
        response=response,
    )
    trace_id = request_runtime.trace_id
    metrics_route_token = request_runtime.metrics_route_token
    request_started = request_runtime.request_started
    timings_ms = request_runtime.timings_ms
    api_key_token = None

    try:
        api_key_token = bind_request_api_key(db, player)
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

        await schedule_prefetch_async_best_effort(
            session_id=payload.session_id,
            trigger="api_next",
            bind=db.get_bind(),
            timings_ms=timings_ms,
            logger=logger,
            run_inference_thread_fn=run_inference_thread,
            schedule_prefetch_fn=schedule_frontier_prefetch,
        )

        return cast(NextResp, result["response"])
    finally:
        reset_bound_request_api_key(api_key_token)
        finalize_request_metrics(
            route="/api/next",
            trace_id=trace_id,
            session_id=payload.session_id,
            request_started=request_started,
            timings_ms=timings_ms,
            metrics_route_token=metrics_route_token,
            logger=logger,
        )
