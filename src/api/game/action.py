"""Freeform action endpoint."""

import logging
from typing import cast

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...models.schemas import ActionRequest, ActionResponse
from ...services.game_logic import render
from ...services.session_service import get_state_manager, save_state
from ...services.storylet_selector import pick_storylet_enhanced
from ...services.storylet_utils import find_storylet_by_location

router = APIRouter()


@router.post("/action", response_model=ActionResponse)
def api_freeform_action(payload: ActionRequest, db: Session = Depends(get_db)):
    """Interpret a freeform player action using natural language."""
    from ...services import world_memory
    from ...services.command_interpreter import interpret_action

    state_manager = get_state_manager(payload.session_id, db)

    current_location = str(state_manager.get_variable("location", "start"))
    current_storylet = find_storylet_by_location(db, current_location)

    result = interpret_action(
        action=payload.action,
        state_manager=state_manager,
        world_memory_module=world_memory,
        current_storylet=current_storylet,
        db=db,
    )

    event_type = world_memory.infer_event_type("freeform_action", result.state_deltas)

    try:
        world_memory.record_event(
            db=db,
            session_id=payload.session_id,
            storylet_id=cast(int, current_storylet.id) if current_storylet else None,
            event_type=event_type,
            summary=f"Player action: {payload.action}. Result: {result.narrative_text[:200]}",
            delta=result.state_deltas,
            state_manager=state_manager,
        )
    except Exception as exc:
        logging.warning("Failed to record action event: %s", exc)
        if result.state_deltas:
            world_memory.apply_event_delta_to_state(state_manager, result.state_deltas)

    save_state(state_manager, db)

    triggered_text = None
    should_trigger = result.should_trigger_storylet or world_memory.should_trigger_storylet(
        event_type,
        result.state_deltas,
    )
    if should_trigger:
        contextual_vars = state_manager.get_contextual_variables()
        triggered = pick_storylet_enhanced(db, state_manager)
        if triggered:
            triggered_text = render(cast(str, triggered.text_template), contextual_vars)

    response = {
        "narrative": result.narrative_text,
        "state_changes": result.state_deltas,
        "choices": [
            {"label": choice.get("label", "Continue"), "set": choice.get("set", {})}
            for choice in result.follow_up_choices
        ],
        "plausible": result.plausible,
        "vars": state_manager.get_contextual_variables(),
    }

    if triggered_text:
        response["triggered_storylet"] = triggered_text

    return response
