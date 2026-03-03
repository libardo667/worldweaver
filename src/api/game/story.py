"""Story progression endpoints."""

import json
import logging
from typing import Any, Dict, List, cast

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...models.schemas import ChoiceOut, NextReq, NextResp
from ...services.game_logic import ensure_storylets, render
from ...services.llm_service import adapt_storylet_to_context
from ...services.session_service import get_state_manager, save_state
from ...services.storylet_selector import pick_storylet_enhanced
from ...services.storylet_utils import normalize_choice

router = APIRouter()


@router.post("/next", response_model=NextResp)
def api_next(
    payload: NextReq,
    response: Response,
    debug_scores: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Get the next storylet for a session with advanced state management."""
    state_manager = get_state_manager(payload.session_id, db)

    for key, value in (payload.vars or {}).items():
        state_manager.set_variable(key, value)

    contextual_vars = state_manager.get_contextual_variables()
    ensure_storylets(db, contextual_vars)
    debug_requested = bool(debug_scores and settings.enable_dev_reset)
    selection_debug: Dict[str, Any] | None = {} if debug_requested else None
    story = pick_storylet_enhanced(
        db,
        state_manager,
        debug_selection=selection_debug,
    )

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

        adaptation_context = {
            "variables": contextual_vars,
            "environment": state_manager.environment.__dict__.copy(),
            "recent_events": recent_event_summaries,
            "state_summary": state_manager.get_state_summary(),
        }
        adapted = adapt_storylet_to_context(story, adaptation_context)
        text = str(adapted.get("text") or render(cast(str, story.text_template), contextual_vars))
        adapted_choices = adapted.get("choices")
        if not isinstance(adapted_choices, list):
            adapted_choices = cast(List[Dict[str, Any]], story.choices or [])
        choices = [
            ChoiceOut(**normalize_choice(c))
            for c in cast(List[Dict[str, Any]], adapted_choices)
        ]
        out = NextResp(text=text, choices=choices, vars=contextual_vars)

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

    save_state(state_manager, db)
    if debug_requested and selection_debug is not None:
        response.headers["X-WorldWeaver-Score-Debug"] = json.dumps(
            selection_debug,
            separators=(",", ":"),
            sort_keys=True,
        )

    return out
