"""Story progression endpoints."""

import logging
from typing import Any, Dict, List, cast

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...models.schemas import ChoiceOut, NextReq, NextResp
from ...services.game_logic import ensure_storylets, render
from ...services.session_service import get_state_manager, save_state
from ...services.storylet_selector import pick_storylet_enhanced
from ...services.storylet_utils import normalize_choice

router = APIRouter()


@router.post("/next", response_model=NextResp)
def api_next(payload: NextReq, db: Session = Depends(get_db)):
    """Get the next storylet for a session with advanced state management."""
    state_manager = get_state_manager(payload.session_id, db)

    for key, value in (payload.vars or {}).items():
        state_manager.set_variable(key, value)

    contextual_vars = state_manager.get_contextual_variables()
    ensure_storylets(db, contextual_vars)
    story = pick_storylet_enhanced(db, state_manager)

    if story is None:
        text = "The tunnel is quiet. Nothing compelling meets the eye."
        choices = [ChoiceOut(label="Wait", set={})]

        if state_manager.environment.danger_level > 3:
            text = "The air feels heavy with danger. Perhaps it is wise to wait and listen."
        elif state_manager.environment.time_of_day == "night":
            text = "The darkness is deep. Something stirs in the shadows, but nothing approaches."

        out = NextResp(text=text, choices=choices, vars=contextual_vars)
    else:
        text = render(cast(str, story.text_template), contextual_vars)
        choices = [
            ChoiceOut(**normalize_choice(c))
            for c in cast(List[Dict[str, Any]], story.choices or [])
        ]
        out = NextResp(text=text, choices=choices, vars=contextual_vars)

        try:
            from ...services.world_memory import record_event

            record_event(
                db=db,
                session_id=payload.session_id,
                storylet_id=cast(int, story.id),
                event_type="storylet_fired",
                summary=f"Storylet '{story.title}' fired",
                delta={},
            )
        except Exception as exc:
            logging.warning("Failed to record storylet event: %s", exc)

    save_state(state_manager, db)
    return out
