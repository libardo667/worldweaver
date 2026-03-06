"""Shared endpoint-to-orchestrator adapters for game routes."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from ...models.schemas import ActionRequest, NextReq
from ...services.game_logic import ensure_storylets, render
from ...services.llm_service import adapt_storylet_to_context, generate_next_beat
from ...services.session_service import get_spatial_navigator, session_mutation_lock
from ...services.storylet_selector import pick_storylet_enhanced
from ...services.storylet_utils import find_storylet_by_location, normalize_choice
from ...services.turn_service import TurnOrchestrator


def run_next_turn_orchestration(
    *,
    db: Session,
    payload: NextReq,
    timings_ms: Dict[str, float],
    debug_scores: bool,
    use_session_lock: bool = True,
    ensure_storylets_fn=ensure_storylets,
    pick_storylet_fn=pick_storylet_enhanced,
    adapt_storylet_fn=adapt_storylet_to_context,
    generate_next_beat_fn=generate_next_beat,
    normalize_choice_fn=normalize_choice,
    render_fn=render,
) -> Dict[str, Any]:
    """Execute canonical next-turn orchestration with optional session locking."""

    def _execute() -> Dict[str, Any]:
        return TurnOrchestrator.process_next_turn(
            db=db,
            payload=payload,
            timings_ms=timings_ms,
            debug_scores=debug_scores,
            ensure_storylets_fn=ensure_storylets_fn,
            pick_storylet_fn=pick_storylet_fn,
            adapt_storylet_fn=adapt_storylet_fn,
            generate_next_beat_fn=generate_next_beat_fn,
            normalize_choice_fn=normalize_choice_fn,
            render_fn=render_fn,
        )

    if use_session_lock:
        with session_mutation_lock(payload.session_id):
            return _execute()
    return _execute()


def run_action_turn_orchestration(
    *,
    db: Session,
    payload: ActionRequest,
    timings_ms: Dict[str, float] | None = None,
    phase_events: List[Tuple[str, Dict[str, Any]]] | None = None,
    ack_line_hint: str | None = None,
    use_session_lock: bool = True,
    get_spatial_navigator_fn=get_spatial_navigator,
    pick_storylet_fn=pick_storylet_enhanced,
    render_fn=render,
    find_storylet_by_location_fn=find_storylet_by_location,
) -> Dict[str, Any]:
    """Execute canonical action-turn orchestration with optional session locking."""

    def _execute() -> Dict[str, Any]:
        return TurnOrchestrator.process_action_turn(
            db=db,
            payload=payload,
            timings_ms=timings_ms,
            phase_events=phase_events,
            ack_line_hint=ack_line_hint,
            get_spatial_navigator_fn=get_spatial_navigator_fn,
            pick_storylet_fn=pick_storylet_fn,
            render_fn=render_fn,
            find_storylet_by_location_fn=find_storylet_by_location_fn,
        )

    if use_session_lock:
        with session_mutation_lock(payload.session_id):
            return _execute()
    return _execute()
