"""Freeform action endpoint."""

import json
import logging
import re
import time
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Storylet
from ...models.schemas import ActionRequest, ActionResponse
from ...services.game_logic import render
from ...services.session_service import get_spatial_navigator, get_state_manager, save_state
from ...services.storylet_selector import pick_storylet_enhanced
from ...services.storylet_utils import find_storylet_by_location

router = APIRouter()
_SEMANTIC_GOAL_PATTERN = re.compile(
    r"\b(?:looking for|look for|find|search for|seeking|where(?:'s| is))\s+(?:the\s+)?([a-z][a-z0-9 _-]{1,60})",
    re.IGNORECASE,
)


def _extract_semantic_goal(action: str) -> str | None:
    match = _SEMANTIC_GOAL_PATTERN.search(str(action or ""))
    if not match:
        return None
    goal = match.group(1).strip(" .,!?:;-")
    return goal or None


def _sse_event(event: str, payload: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _provisional_action_text(action: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(action or "").strip())
    if len(cleaned) > 180:
        cleaned = f"{cleaned[:177]}..."
    return (
        f'You attempt: "{cleaned}". '
        "The world takes a breath as consequences begin to settle..."
    )


def _stream_provisional_chunks(action: str):
    provisional = _provisional_action_text(action)
    words = provisional.split()
    streamed: list[str] = []
    for word in words:
        streamed.append(word)
        yield _sse_event("draft_chunk", {"text": " ".join(streamed)})
        time.sleep(0.012)


def _resolve_freeform_action(payload: ActionRequest, db: Session) -> Dict[str, Any]:
    """Interpret a freeform action and return canonical ActionResponse payload."""
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
    semantic_goal = _extract_semantic_goal(payload.action)

    for beat in result.suggested_beats:
        if isinstance(beat, dict):
            state_manager.add_narrative_beat(beat)

    goal_update = None
    if isinstance(result.reasoning_metadata, dict):
        raw_goal_update = result.reasoning_metadata.get("goal_update")
        if isinstance(raw_goal_update, dict):
            goal_update = raw_goal_update
    if goal_update:
        state_manager.apply_goal_update(goal_update, source="action_interpreter")

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
            metadata=result.reasoning_metadata,
        )
    except Exception as exc:
        logging.warning("Failed to record action event: %s", exc)
        if result.state_deltas:
            world_memory.apply_event_delta_to_state(state_manager, result.state_deltas)

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

    raw_choices = result.follow_up_choices if isinstance(result.follow_up_choices, list) else []
    choices = []
    for choice in raw_choices[:3]:
        if not isinstance(choice, dict):
            continue
        choice_set = choice.get("set", {})
        if not isinstance(choice_set, dict):
            choice_set = {}
        choices.append(
            {
                "label": str(choice.get("label", "Continue")),
                "set": choice_set,
            }
        )
    if not choices:
        choices = [{"label": "Continue", "set": {}}]

    state_changes = result.state_deltas if isinstance(result.state_deltas, dict) else {}
    narrative_text = str(result.narrative_text or "")
    if semantic_goal:
        try:
            from ...services.semantic_selector import compute_player_context_vector

            spatial_nav = get_spatial_navigator(db)
            effective_storylet = current_storylet
            if effective_storylet is None:
                positioned_ids = list(spatial_nav.storylet_positions.keys())
                if positioned_ids:
                    effective_storylet = db.query(Storylet).filter(Storylet.id.in_(positioned_ids)).first()
            if effective_storylet is None:
                raise ValueError("No positioned storylet available for semantic hint")

            context_vector = compute_player_context_vector(state_manager, world_memory, db)
            goal_hint = spatial_nav.get_semantic_goal_hint(
                current_storylet_id=cast(int, effective_storylet.id),
                player_vars=state_manager.get_contextual_variables(),
                semantic_goal=semantic_goal,
                context_vector=context_vector,
            )
            if goal_hint and goal_hint.get("hint"):
                narrative_text = f"{narrative_text} {goal_hint['hint']}".strip()
        except Exception as exc:
            logging.debug("Could not resolve semantic goal hint: %s", exc)

    response = {
        "narrative": narrative_text,
        "state_changes": state_changes,
        "choices": choices,
        "plausible": bool(result.plausible),
        "vars": state_manager.get_contextual_variables(),
    }

    if triggered_text:
        response["triggered_storylet"] = triggered_text

    save_state(state_manager, db)

    return response


@router.post("/action", response_model=ActionResponse)
def api_freeform_action(payload: ActionRequest, db: Session = Depends(get_db)):
    """Interpret a freeform player action using natural language."""
    return _resolve_freeform_action(payload, db)


@router.post("/action/stream")
def api_freeform_action_stream(payload: ActionRequest, db: Session = Depends(get_db)):
    """Stream provisional action narration, then emit the final canonical response."""

    def _event_stream():
        for chunk in _stream_provisional_chunks(payload.action):
            yield chunk
        try:
            final_payload = _resolve_freeform_action(payload, db)
            yield _sse_event("final", final_payload)
        except Exception as exc:
            logging.exception("Action streaming failed")
            yield _sse_event("error", {"detail": str(exc)})

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
