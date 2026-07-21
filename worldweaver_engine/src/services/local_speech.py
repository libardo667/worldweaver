# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Canonical rules for durable public speech at one exact place."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models import LocationChat, SessionVars
from .clock import utc_naive
from .event_submission import WorldEventCommand, submit_world_event
from .live_signals import notify_live_signal
from .world_memory import EVENT_TYPE_UTTERANCE

_AGENT_SLUG_RE = re.compile(r"^([a-z][a-z0-9_]*)[-_]\d{8}")


class LocalSpeechError(ValueError):
    """A safe, typed refusal from the local-speech boundary."""

    def __init__(self, code: str, detail: str, *, status_code: int):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class LocalSpeechReceipt:
    success: bool
    id: int
    ts: str | None

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)


def _session_variables(raw_payload: Any) -> dict[str, Any]:
    if not isinstance(raw_payload, dict):
        return {}
    nested_vars = raw_payload.get("variables")
    if raw_payload.get("_v") == 2 and isinstance(nested_vars, dict):
        return nested_vars
    return raw_payload


def _display_name(session_id: str, variables: dict[str, Any]) -> str:
    match = _AGENT_SLUG_RE.match(session_id)
    if match:
        return " ".join(word.capitalize() for word in match.group(1).split("_"))

    player_role = str(variables.get("player_role") or "").strip()
    if player_role:
        name_part = (
            player_role.split(" — ")[0].strip() if " — " in player_role else player_role
        )
        if name_part:
            return name_part
    return session_id[:12]


def _utterance_event_delta(
    *,
    speaker_name: str,
    location: str,
    message: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "speaker": speaker_name,
        "channel": location,
        "spatial_nodes": {
            location: {
                "last_public_speaker": speaker_name,
                "last_public_utterance": message,
                "last_public_activity_type": "utterance",
                "last_public_activity_summary": summary,
            }
        },
        "__world_facts__": {
            "facts": [
                {
                    "subject": speaker_name,
                    "subject_type": "entity",
                    "predicate": "spoke_at",
                    "value": location,
                    "location": location,
                    "summary": summary,
                    "confidence": 0.6,
                }
            ],
            "parser_mode": "structured",
        },
    }


def post_local_speech(
    db: Session,
    *,
    session_id: str,
    location: str,
    message: str,
    now: datetime | None = None,
) -> LocalSpeechReceipt:
    """Record one public utterance and its world-memory consequences together."""

    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id or len(normalized_session_id) > 64:
        raise LocalSpeechError(
            "invalid_session",
            "Session ID must contain 1 to 64 characters.",
            status_code=422,
        )

    normalized_message = str(message or "").strip()
    if not normalized_message:
        raise LocalSpeechError(
            "empty_message", "Message cannot be empty.", status_code=400
        )
    if len(normalized_message) > 500:
        raise LocalSpeechError(
            "message_too_long",
            "Message must contain no more than 500 characters.",
            status_code=422,
        )

    requested_location = str(location or "").strip()
    if not requested_location or len(requested_location) > 200:
        raise LocalSpeechError(
            "invalid_location",
            "Location must contain 1 to 200 characters.",
            status_code=422,
        )

    session_row = db.get(SessionVars, normalized_session_id)
    if session_row is None:
        raise LocalSpeechError(
            "session_not_found", "Session not found.", status_code=404
        )

    variables = _session_variables(session_row.vars)
    session_location = str(variables.get("location") or "").strip()
    if not session_location:
        raise LocalSpeechError(
            "session_location_missing",
            "Session has no current location.",
            status_code=409,
        )
    if session_location != requested_location:
        raise LocalSpeechError(
            "remote_speech_forbidden",
            "You can only speak where you are standing.",
            status_code=409,
        )

    display_name = _display_name(normalized_session_id, variables)
    row = LocationChat(
        location=session_location,
        session_id=normalized_session_id,
        actor_id=str(session_row.actor_id or variables.get("actor_id") or "").strip()
        or None,
        display_name=display_name,
        message=normalized_message,
        created_at=utc_naive(now) if now is not None else None,
    )
    summary = f"{display_name} said: {normalized_message}"

    try:
        db.add(row)
        db.flush()
        submit_world_event(
            db,
            WorldEventCommand(
                session_id=normalized_session_id,
                event_type=EVENT_TYPE_UTTERANCE,
                summary=summary,
                delta=_utterance_event_delta(
                    speaker_name=display_name,
                    location=session_location,
                    message=normalized_message,
                    summary=summary,
                ),
                metadata={"surface": "chat", "channel": session_location},
                preserve_event_type=True,
                defer_commit=True,
                occurred_at=now,
            ),
        )
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        raise LocalSpeechError(
            "speech_persistence_failed",
            "Speech could not be recorded.",
            status_code=503,
        ) from exc

    notify_live_signal()
    return LocalSpeechReceipt(
        success=True,
        id=int(row.id),
        ts=row.created_at.isoformat() if row.created_at else None,
    )
