"""Story progression endpoints."""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, cast

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...models.schemas import ChoiceOut, NextReq, NextResp
from ...services.game_logic import ensure_storylets, render
from ...services.llm_client import reset_trace_id, set_trace_id
from ...services.llm_service import adapt_storylet_to_context
from ...services.prefetch_service import schedule_frontier_prefetch
from ...services.session_service import get_state_manager, save_state
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
    trace_id = uuid.uuid4().hex
    trace_token = set_trace_id(trace_id)
    response.headers["X-WW-Trace-Id"] = trace_id
    request_started = time.perf_counter()
    timings_ms: Dict[str, float] = {}
    state_manager = get_state_manager(payload.session_id, db)

    try:
        set_vars_started = time.perf_counter()
        for key, value in (payload.vars or {}).items():
            state_manager.set_variable(key, value)
        timings_ms["set_vars"] = round((time.perf_counter() - set_vars_started) * 1000.0, 3)

        context_started = time.perf_counter()
        contextual_vars = state_manager.get_contextual_variables()
        timings_ms["get_contextual_vars"] = round((time.perf_counter() - context_started) * 1000.0, 3)

        ensure_started = time.perf_counter()
        ensure_storylets(db, contextual_vars)
        timings_ms["ensure_storylets"] = round((time.perf_counter() - ensure_started) * 1000.0, 3)

        debug_requested = bool(debug_scores and settings.enable_dev_reset)
        selection_debug: Dict[str, Any] | None = {} if debug_requested else None
        select_started = time.perf_counter()
        story = pick_storylet_enhanced(
            db,
            state_manager,
            debug_selection=selection_debug,
        )
        timings_ms["pick_storylet"] = round((time.perf_counter() - select_started) * 1000.0, 3)

        if story is None:
            text = "The tunnel is quiet. Nothing compelling meets the eye."
            choices = [ChoiceOut(label="Wait", set={})]

            if state_manager.environment.danger_level > 3:
                text = "The air feels heavy with danger. Perhaps it is wise to wait and listen."
            elif state_manager.environment.time_of_day == "night":
                text = "The darkness is deep. Something stirs in the shadows, but nothing approaches."

            out = NextResp(text=text, choices=choices, vars=contextual_vars)
        else:
            recent_event_summaries: List[str] = []
            history_started = time.perf_counter()
            try:
                from ...services.world_memory import get_world_history

                recent_events = get_world_history(
                    db,
                    session_id=payload.session_id,
                    limit=3,
                )
                recent_event_summaries = [
                    str(event.summary).strip()
                    for event in recent_events
                    if str(event.summary).strip()
                ]
            except Exception as exc:
                logging.debug("Could not load recent world history for adaptation: %s", exc)
            finally:
                timings_ms["load_recent_history"] = round((time.perf_counter() - history_started) * 1000.0, 3)

            adaptation_context = {
                "variables": contextual_vars,
                "environment": state_manager.environment.__dict__.copy(),
                "recent_events": recent_event_summaries,
                "state_summary": state_manager.get_state_summary(),
            }
            adapt_started = time.perf_counter()
            adapted = adapt_storylet_to_context(story, adaptation_context)
            timings_ms["adapt_storylet"] = round((time.perf_counter() - adapt_started) * 1000.0, 3)
            text = str(adapted.get("text") or render(cast(str, story.text_template), contextual_vars))
            adapted_choices = adapted.get("choices")
            if not isinstance(adapted_choices, list):
                adapted_choices = cast(List[Dict[str, Any]], story.choices or [])
            choices = [
                ChoiceOut(**normalize_choice(c))
                for c in cast(List[Dict[str, Any]], adapted_choices)
            ]
            out = NextResp(text=text, choices=choices, vars=contextual_vars)

            record_started = time.perf_counter()
            try:
                from ...services.world_memory import (
                    EVENT_TYPE_STORYLET_FIRED,
                    record_event,
                )

                record_event(
                    db=db,
                    session_id=payload.session_id,
                    storylet_id=cast(int, story.id),
                    event_type=EVENT_TYPE_STORYLET_FIRED,
                    summary=f"Storylet '{story.title}' fired",
                    delta={},
                )
            except Exception as exc:
                logging.warning("Failed to record storylet event: %s", exc)
            finally:
                timings_ms["record_storylet_event"] = round((time.perf_counter() - record_started) * 1000.0, 3)

        save_started = time.perf_counter()
        save_state(state_manager, db)
        timings_ms["save_state"] = round((time.perf_counter() - save_started) * 1000.0, 3)
        if debug_requested and selection_debug is not None:
            response.headers["X-WorldWeaver-Score-Debug"] = json.dumps(
                selection_debug,
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
            timings_ms["schedule_prefetch"] = round((time.perf_counter() - prefetch_started) * 1000.0, 3)

        return out
    finally:
        logger.info(
            json.dumps(
                {
                    "event": "request_timing",
                    "route": "/api/next",
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
