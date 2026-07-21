# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Private actor-addressed correspondence with explicit acknowledgement."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import DirectMessage, Player, ResidentAuthority, SessionVars


class CorrespondenceError(ValueError):
    """A safe refusal from the private correspondence boundary."""

    def __init__(self, code: str, message: str, *, status_code: int):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class SendCorrespondenceCommand:
    sender_session_id: str
    recipient_actor_id: str
    body: str


@dataclass(frozen=True, slots=True)
class CorrespondenceReceipt:
    success: bool
    message_id: int
    sender_actor_id: str
    recipient_actor_id: str
    sent_at: str | None

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CorrespondenceItem:
    message_id: int
    sender_actor_id: str
    sender_name: str
    recipient_actor_id: str
    body: str
    sent_at: str | None
    acknowledged_at: str | None

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CorrespondenceInbox:
    session_id: str
    actor_id: str
    messages: tuple[CorrespondenceItem, ...]

    def as_payload(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "actor_id": self.actor_id,
            "messages": [message.as_payload() for message in self.messages],
            "count": len(self.messages),
        }


@dataclass(frozen=True, slots=True)
class CorrespondenceAcknowledgement:
    session_id: str
    actor_id: str
    acknowledged_ids: tuple[int, ...]

    def as_payload(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "actor_id": self.actor_id,
            "acknowledged_ids": list(self.acknowledged_ids),
            "acknowledged_count": len(self.acknowledged_ids),
        }


def _session_actor(db: Session, session_id: str) -> tuple[SessionVars, str]:
    normalized = str(session_id or "").strip()
    if not normalized or len(normalized) > 64:
        raise CorrespondenceError(
            "invalid_session",
            "Session ID must contain 1 to 64 characters.",
            status_code=422,
        )
    row = db.get(SessionVars, normalized)
    if row is None:
        raise CorrespondenceError(
            "session_not_found", "Session not found.", status_code=404
        )
    actor_id = str(row.actor_id or "").strip()
    if not actor_id:
        raise CorrespondenceError(
            "durable_actor_required",
            "Correspondence requires a session bound to a durable actor.",
            status_code=409,
        )
    return row, actor_id


def _session_variables(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    nested = raw.get("variables")
    if raw.get("_v") == 2 and isinstance(nested, dict):
        return nested
    return raw


def _sender_name(row: SessionVars) -> str:
    variables = _session_variables(row.vars)
    raw = str(
        variables.get("name")
        or variables.get("player_role")
        or variables.get("player_name")
        or row.session_id
        or ""
    ).strip()
    if " — " in raw:
        raw = raw.split(" — ", 1)[0].strip()
    return raw[:60] or "Unknown actor"


def _known_actor(db: Session, actor_id: str) -> bool:
    return bool(
        db.query(Player.id).filter(Player.actor_id == actor_id).first()
        or db.get(ResidentAuthority, actor_id) is not None
        or db.query(SessionVars.session_id)
        .filter(SessionVars.actor_id == actor_id)
        .first()
    )


def send_correspondence(
    db: Session,
    *,
    command: SendCorrespondenceCommand,
) -> CorrespondenceReceipt:
    """Store one private message between durable actors."""

    sender_row, sender_actor_id = _session_actor(db, command.sender_session_id)
    recipient_actor_id = str(command.recipient_actor_id or "").strip()
    if not recipient_actor_id or len(recipient_actor_id) > 36:
        raise CorrespondenceError(
            "invalid_recipient",
            "Recipient actor ID must contain 1 to 36 characters.",
            status_code=422,
        )
    if not _known_actor(db, recipient_actor_id):
        raise CorrespondenceError(
            "recipient_not_found",
            "No local durable actor matches that recipient.",
            status_code=404,
        )
    body = str(command.body or "").strip()
    if not body:
        raise CorrespondenceError(
            "empty_message", "Correspondence cannot be empty.", status_code=400
        )
    if len(body) > 4000:
        raise CorrespondenceError(
            "message_too_long",
            "Correspondence must contain no more than 4000 characters.",
            status_code=422,
        )

    row = DirectMessage(
        from_name=_sender_name(sender_row),
        from_session_id=str(sender_row.session_id),
        sender_actor_id=sender_actor_id,
        recipient_actor_id=recipient_actor_id,
        to_name=recipient_actor_id,
        body=body,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        raise CorrespondenceError(
            "correspondence_persistence_failed",
            "Correspondence could not be recorded.",
            status_code=503,
        ) from exc

    return CorrespondenceReceipt(
        success=True,
        message_id=int(row.id),
        sender_actor_id=sender_actor_id,
        recipient_actor_id=recipient_actor_id,
        sent_at=row.sent_at.isoformat() if row.sent_at else None,
    )


def pending_correspondence(
    db: Session,
    *,
    session_id: str,
    limit: int = 50,
) -> CorrespondenceInbox:
    """Return unacknowledged mail without changing its delivery state."""

    _, actor_id = _session_actor(db, session_id)
    bounded_limit = max(1, min(100, int(limit)))
    rows = (
        db.query(DirectMessage)
        .filter(
            DirectMessage.recipient_actor_id == actor_id,
            DirectMessage.acknowledged_at.is_(None),
        )
        .order_by(DirectMessage.id.asc())
        .limit(bounded_limit)
        .all()
    )
    return CorrespondenceInbox(
        session_id=str(session_id),
        actor_id=actor_id,
        messages=tuple(
            CorrespondenceItem(
                message_id=int(row.id),
                sender_actor_id=str(row.sender_actor_id or ""),
                sender_name=str(row.from_name or ""),
                recipient_actor_id=str(row.recipient_actor_id or ""),
                body=str(row.body or ""),
                sent_at=row.sent_at.isoformat() if row.sent_at else None,
                acknowledged_at=(
                    row.acknowledged_at.isoformat() if row.acknowledged_at else None
                ),
            )
            for row in rows
        ),
    )


def acknowledge_correspondence(
    db: Session,
    *,
    session_id: str,
    message_ids: Iterable[int],
) -> CorrespondenceAcknowledgement:
    """Acknowledge only messages addressed to the caller's durable actor."""

    _, actor_id = _session_actor(db, session_id)
    normalized_ids = tuple(
        dict.fromkeys(
            int(message_id)
            for message_id in message_ids
            if isinstance(message_id, int)
            and not isinstance(message_id, bool)
            and message_id > 0
        )
    )
    if not normalized_ids:
        return CorrespondenceAcknowledgement(
            session_id=str(session_id),
            actor_id=actor_id,
            acknowledged_ids=(),
        )

    rows = (
        db.query(DirectMessage)
        .filter(
            DirectMessage.id.in_(normalized_ids),
            DirectMessage.recipient_actor_id == actor_id,
        )
        .order_by(DirectMessage.id.asc())
        .all()
    )
    found_ids = {int(row.id) for row in rows}
    if found_ids != set(normalized_ids):
        db.rollback()
        raise CorrespondenceError(
            "message_not_owned",
            "One or more messages are not addressed to this actor.",
            status_code=403,
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    changed: list[int] = []
    try:
        for row in rows:
            if row.acknowledged_at is None:
                row.acknowledged_at = now
                row.read_at = now
                changed.append(int(row.id))
        db.commit()
    except Exception as exc:
        db.rollback()
        raise CorrespondenceError(
            "acknowledgement_persistence_failed",
            "Correspondence acknowledgement could not be recorded.",
            status_code=503,
        ) from exc

    return CorrespondenceAcknowledgement(
        session_id=str(session_id),
        actor_id=actor_id,
        acknowledged_ids=tuple(changed),
    )


def correspondence_threads(
    db: Session, *, session_id: str
) -> tuple[dict[str, Any], ...]:
    """Return complete private threads for one durable actor."""

    _, actor_id = _session_actor(db, session_id)
    rows = (
        db.query(DirectMessage)
        .filter(
            or_(
                DirectMessage.recipient_actor_id == actor_id,
                DirectMessage.sender_actor_id == actor_id,
            )
        )
        .order_by(DirectMessage.sent_at.asc(), DirectMessage.id.asc())
        .all()
    )
    threads: dict[str, dict[str, Any]] = {}
    for row in rows:
        inbound = str(row.recipient_actor_id or "") == actor_id
        counterpart_id = str(
            row.sender_actor_id if inbound else row.recipient_actor_id or ""
        )
        if not counterpart_id:
            continue
        thread = threads.setdefault(
            counterpart_id,
            {
                "counterpart_actor_id": counterpart_id,
                "counterpart_name": str(row.from_name or "") if inbound else "",
                "messages": [],
                "unacknowledged_count": 0,
            },
        )
        thread["messages"].append(
            {
                "message_id": int(row.id),
                "direction": "inbound" if inbound else "outbound",
                "sender_actor_id": str(row.sender_actor_id or ""),
                "body": str(row.body or ""),
                "sent_at": row.sent_at.isoformat() if row.sent_at else None,
                "acknowledged_at": (
                    row.acknowledged_at.isoformat() if row.acknowledged_at else None
                ),
            }
        )
        if inbound and row.acknowledged_at is None:
            thread["unacknowledged_count"] += 1
    return tuple(threads.values())
