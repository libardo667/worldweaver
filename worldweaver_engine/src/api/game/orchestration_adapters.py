# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Shared endpoint-to-orchestrator adapters for game routes."""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from ...models.schemas import ActionRequest
from ...services.session_service import (
    get_state_manager,
    session_mutation_lock,
)
from ...services.turn.narration import render
from ...services.turn_service import TurnOrchestrator

logger = logging.getLogger(__name__)


def run_action_turn_orchestration(
    *,
    db: Session,
    payload: ActionRequest,
    timings_ms: Dict[str, float] | None = None,
    phase_events: List[Tuple[str, Dict[str, Any]]] | None = None,
    ack_line_hint: str | None = None,
    actor_inference_policy=None,
    use_session_lock: bool = True,
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
            actor_inference_policy=actor_inference_policy,
            render_fn=render_fn,
        )

    def _execute_with_guard() -> Dict[str, Any]:
        state_manager = get_state_manager(payload.session_id, db)
        initial_state = deepcopy(state_manager.export_state())
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
