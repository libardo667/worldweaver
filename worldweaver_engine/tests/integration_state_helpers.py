"""Shared helpers for integration tests that manipulate session state."""

from __future__ import annotations

from typing import Any

from src.services.session_service import _state_managers, get_state_manager, save_state
from src.services.world_memory import record_event


def get_manager(db: Any, session_id: str):
    return get_state_manager(session_id, db)


def save_manager(db: Any, manager: Any) -> None:
    save_state(manager, db)


def save_and_reload_session(db: Any, session_id: str):
    manager = _state_managers[session_id]
    save_state(manager, db)
    _state_managers.pop(session_id, None)
    return get_state_manager(session_id, db)


def record_projection_event(
    db: Any,
    *,
    source_session_id: str,
    summary: str,
    delta: dict[str, Any],
) -> None:
    record_event(
        db,
        source_session_id,
        None,
        "freeform_action",
        summary,
        delta=delta,
    )
