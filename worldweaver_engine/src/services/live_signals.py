# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Durable, exact-place signals for an attached participant.

The first signal family is local public speech.  ``LocationChat.id`` is already
an append-only, increasing sequence inside one shard, so this service exposes a
cursor over that sequence instead of copying speech into a second queue.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..models import LocationChat, SessionVars
from .federation_identity import current_shard_id

_signal_condition = threading.Condition()
_signal_revision = 0


def current_live_signal_revision() -> int:
    with _signal_condition:
        return _signal_revision


def notify_live_signal() -> None:
    """Wake local waiters; the database cursor remains the source of truth."""

    global _signal_revision
    with _signal_condition:
        _signal_revision += 1
        _signal_condition.notify_all()


def wait_for_live_signal_change(*, after_revision: int, timeout: float) -> bool:
    """Wait for any local signal write and report whether the revision changed."""

    bounded_timeout = max(0.0, min(25.0, float(timeout)))
    with _signal_condition:
        return _signal_condition.wait_for(
            lambda: _signal_revision != after_revision,
            timeout=bounded_timeout,
        )


@dataclass(frozen=True, slots=True)
class LiveSignalError(ValueError):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def _session_vars(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _message_payload(row: LocationChat) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "type": "local_speech",
        "location": str(row.location or ""),
        "session_id": str(row.session_id or ""),
        "actor_id": str(row.actor_id or ""),
        "display_name": str(row.display_name or ""),
        "message": str(row.message or ""),
        "occurred_at": row.created_at.isoformat() if row.created_at else None,
    }


def read_live_signals(
    db: Session,
    *,
    session_id: str,
    after_id: int | None,
    cursor_shard: str | None,
    cursor_location: str | None,
    limit: int,
) -> dict[str, Any]:
    """Read one participant's new exact-place signals and advance its cursor.

    A request without a cursor establishes one at the current high-water mark;
    old room chat is not replayed as present-time hearing.  A cursor from a
    different shard or location is reset just as explicitly.
    """

    normalized_session_id = str(session_id or "").strip()
    session_row = db.get(SessionVars, normalized_session_id)
    if session_row is None:
        raise LiveSignalError("session_not_found", "Session not found.")

    variables = _session_vars(session_row.vars)
    location = str(variables.get("location") or "").strip()
    if not location:
        raise LiveSignalError(
            "session_location_missing", "Session has no current location."
        )

    shard_id = current_shard_id()
    high_water = int(
        db.query(func.max(LocationChat.id))
        .filter(LocationChat.location == location)
        .scalar()
        or 0
    )
    cursor_parts = (
        after_id is not None,
        bool(cursor_shard),
        bool(cursor_location),
    )
    if any(cursor_parts) and not all(cursor_parts):
        raise LiveSignalError(
            "incomplete_cursor",
            "after, cursor_shard, and cursor_location must be supplied together.",
        )

    status = "current"
    retention = "complete"
    if after_id is None:
        status = "established"
    elif cursor_shard != shard_id or cursor_location != location:
        status = "scope_changed"
    elif after_id > high_water:
        status = "retention_gap"
        retention = "gap"

    if status != "current":
        return {
            "version": 1,
            "cursor_status": status,
            "retention": retention,
            "cursor": {
                "shard_id": shard_id,
                "location": location,
                "after_id": high_water,
            },
            "events": [],
            "has_more": False,
        }

    actor_id = str(session_row.actor_id or variables.get("actor_id") or "").strip()
    query = db.query(LocationChat).filter(
        LocationChat.location == location,
        LocationChat.id > int(after_id),
        LocationChat.id <= high_water,
        LocationChat.session_id != normalized_session_id,
    )
    if actor_id:
        query = query.filter(
            or_(LocationChat.actor_id.is_(None), LocationChat.actor_id != actor_id)
        )
    rows = query.order_by(LocationChat.id.asc()).limit(int(limit) + 1).all()
    has_more = len(rows) > limit
    visible_rows = rows[:limit]
    next_id = int(visible_rows[-1].id) if has_more else high_water
    return {
        "version": 1,
        "cursor_status": status,
        "retention": retention,
        "cursor": {
            "shard_id": shard_id,
            "location": location,
            "after_id": next_id,
        },
        "events": [_message_payload(row) for row in visible_rows],
        "has_more": has_more,
    }
