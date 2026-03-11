"""Shared endpoint-to-orchestrator adapters for game routes."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from ...models.schemas import ActionRequest, NextReq
from ...services.game_logic import ensure_storylets, render
from ...services.llm_service import adapt_storylet_to_context, generate_next_beat
from ...services.prefetch_service import invalidate_projection_for_session
from ...services.session_service import (
    get_spatial_navigator,
    get_state_manager,
    session_mutation_lock,
)
from ...services.storylet_selector import pick_storylet_enhanced
from ...services.storylet_utils import normalize_choice  # used by run_next_turn_orchestration
from ...services.turn_service import TurnOrchestrator

logger = logging.getLogger(__name__)


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

    def _execute_with_guard() -> Dict[str, Any]:
        state_manager = get_state_manager(payload.session_id, db)
        initial_state = state_manager.export_state()
        try:
            result = _execute()
        except Exception:
            db.rollback()
            try:
                state_manager.import_state(initial_state)
            except Exception as restore_exc:
                logger.warning("Failed to restore state snapshot for session=%s: %s", payload.session_id, restore_exc)
            raise

        response_payload = result.get("response")
        response_vars = getattr(response_payload, "vars", None)
        selected_projection_id = None
        if isinstance(response_vars, dict):
            diag = response_vars.get("_ww_diag", {})
            if isinstance(diag, dict):
                raw_selected_projection = diag.get("projection_seed_storylet_id")
                try:
                    if raw_selected_projection is not None:
                        selected_projection_id = int(raw_selected_projection)
                except (TypeError, ValueError):
                    selected_projection_id = None

        invalidation = invalidate_projection_for_session(
            payload.session_id,
            selected_projection_id=selected_projection_id,
            commit_status="committed",
        )
        if isinstance(response_vars, dict):
            diag = response_vars.get("_ww_diag", {})
            if not isinstance(diag, dict):
                diag = {}
            diag.update(invalidation)
            response_vars["_ww_diag"] = diag
            setattr(response_payload, "vars", response_vars)
            setattr(response_payload, "diagnostics", dict(diag))

        return result

    if use_session_lock:
        with session_mutation_lock(payload.session_id):
            return _execute_with_guard()
    return _execute_with_guard()


def run_action_turn_orchestration(
    *,
    db: Session,
    payload: ActionRequest,
    timings_ms: Dict[str, float] | None = None,
    phase_events: List[Tuple[str, Dict[str, Any]]] | None = None,
    ack_line_hint: str | None = None,
    use_session_lock: bool = True,
    get_spatial_navigator_fn=get_spatial_navigator,
    render_fn=render,
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
            render_fn=render_fn,
        )

    def _execute_with_guard() -> Dict[str, Any]:
        state_manager = get_state_manager(payload.session_id, db)
        initial_state = state_manager.export_state()
        try:
            resolved = _execute()
        except Exception:
            db.rollback()
            try:
                state_manager.import_state(initial_state)
            except Exception as restore_exc:
                logger.warning("Failed to restore state snapshot for session=%s: %s", payload.session_id, restore_exc)
            raise

        return resolved

    if use_session_lock:
        with session_mutation_lock(payload.session_id):
            return _execute_with_guard()
    return _execute_with_guard()
