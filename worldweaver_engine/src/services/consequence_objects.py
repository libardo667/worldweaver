# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Canonical durable objects and their append-only consequence receipts.

This domain is separate from the old session-local inventory. Objects here are
shared world facts. They can change only through typed functions in this module;
narrative prose and ordinary world-event deltas cannot mutate these tables.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import ConsequenceReceipt, DurableObject, SessionVars, StoopObjectEntry
from .event_submission import WorldEventCommand, structural_event_idempotency_key, submit_world_event
from .federation_identity import current_shard_id
from .shard_experience import GameCapability, GameCapabilityUnavailable, require_game_capabilities

_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class ConsequenceDomainError(ValueError):
    """A safe, typed failure from the durable-object command boundary."""

    def __init__(self, code: str, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class ActorContext:
    session_id: str
    actor_id: str
    location: str


@dataclass(frozen=True)
class ConsequenceResult:
    object: dict[str, Any]
    receipt: dict[str, Any]
    replayed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "replayed": self.replayed,
            "object": self.object,
            "receipt": self.receipt,
        }


def _session_variables(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    nested = raw.get("variables")
    if raw.get("_v") == 2 and isinstance(nested, dict):
        return dict(nested)
    return dict(raw)


def _actor_context(db: Session, session_id: str) -> ActorContext:
    normalized_session = str(session_id or "").strip()
    if not _SESSION_RE.fullmatch(normalized_session):
        raise ConsequenceDomainError("invalid_session", "Invalid session ID.", status_code=422)
    row = db.get(SessionVars, normalized_session)
    if row is None:
        raise ConsequenceDomainError("session_not_found", "Session not found.", status_code=404)
    actor_id = str(row.actor_id or "").strip()
    if not actor_id:
        raise ConsequenceDomainError("actor_identity_required", "Session has no stable actor identity.")
    location = str(_session_variables(row.vars).get("location") or "").strip()
    if not location:
        raise ConsequenceDomainError("location_required", "Session has no current location.")
    return ActorContext(session_id=normalized_session, actor_id=actor_id, location=location)


def consequence_actor_context(db: Session, session_id: str) -> ActorContext:
    """Resolve the stable actor, session, and exact place for consequence services."""

    return _actor_context(db, session_id)


def _idempotency_key(value: str) -> str:
    normalized = str(value or "").strip()
    if not _IDEMPOTENCY_RE.fullmatch(normalized):
        raise ConsequenceDomainError(
            "invalid_idempotency_key",
            "Idempotency key must use only letters, digits, dot, underscore, colon, or hyphen.",
            status_code=422,
        )
    return normalized


def consequence_idempotency_key(value: str) -> str:
    """Validate a caller retry key for a structured consequence command."""

    return _idempotency_key(value)


def _require_capabilities(*capabilities: GameCapability) -> None:
    try:
        require_game_capabilities(*capabilities)
    except GameCapabilityUnavailable as exc:
        raise ConsequenceDomainError("game_capability_unavailable", str(exc), status_code=403) from exc


def require_consequence_capabilities(*capabilities: GameCapability) -> None:
    """Apply the ordinary-shard opt-in boundary to another consequence service."""

    _require_capabilities(*capabilities)


def durable_object_payload(row: DurableObject) -> dict[str, Any]:
    """Return the stable public fact shared by human and resident callers."""

    if row.custodian_actor_id:
        attachment = {"kind": "custody", "actor_id": str(row.custodian_actor_id)}
    else:
        attachment = {"kind": "place", "location": str(row.location or "")}
    return {
        "object_id": str(row.object_id),
        "name": str(row.name),
        "description": str(row.description or ""),
        "object_kind": str(row.object_kind),
        "status": str(row.status),
        "attachment": attachment,
        "origin_shard_id": str(row.origin_shard_id),
        "provenance": {
            "kind": str(row.provenance_kind),
            "ref": str(row.provenance_ref or ""),
            "created_by_actor_id": str(row.created_by_actor_id),
            "world_event_id": int(row.provenance_event_id) if row.provenance_event_id is not None else None,
        },
        "properties": dict(row.properties_json or {}),
        "revision": int(row.revision or 1),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def consequence_receipt_payload(row: ConsequenceReceipt) -> dict[str, Any]:
    payload = dict(row.payload_json or {})
    return {
        "receipt_id": str(row.receipt_id),
        "operation": str(row.operation),
        "object_id": str(row.object_id),
        "world_event_id": int(row.world_event_id),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "before": payload.get("before"),
        "after": payload.get("after"),
        "details": dict(payload.get("details") or {}),
    }


def _result_from_receipt(row: ConsequenceReceipt, *, replayed: bool) -> ConsequenceResult:
    payload = dict(row.payload_json or {})
    return ConsequenceResult(
        object=dict(payload.get("after") or {}),
        receipt=consequence_receipt_payload(row),
        replayed=replayed,
    )


def _existing_receipt(
    db: Session,
    *,
    actor_id: str,
    idempotency_key: str,
    operation: str,
    object_id: str | None = None,
) -> ConsequenceReceipt | None:
    row = (
        db.query(ConsequenceReceipt)
        .filter(
            ConsequenceReceipt.actor_id == actor_id,
            ConsequenceReceipt.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if row is None:
        return None
    if row.operation != operation or (object_id is not None and row.object_id != object_id):
        raise ConsequenceDomainError(
            "idempotency_conflict",
            "That idempotency key was already used for a different consequence command.",
        )
    return row


def _locked_object(db: Session, object_id: str) -> DurableObject:
    normalized = str(object_id or "").strip()
    row = db.query(DurableObject).filter(DurableObject.object_id == normalized).with_for_update().one_or_none()
    if row is None or row.status != "active":
        raise ConsequenceDomainError("object_not_found", "Durable object not found.", status_code=404)
    return row


def _complete_consequence(
    db: Session,
    *,
    context: ActorContext,
    idempotency_key: str,
    operation: str,
    object_row: DurableObject,
    before: Mapping[str, Any] | None,
    summary: str,
    details: Mapping[str, Any],
    provenance_event: bool = False,
) -> ConsequenceResult:
    event_receipt = submit_world_event(
        db,
        WorldEventCommand(
            session_id=context.session_id,
            event_type=operation,
            summary=summary,
            delta={
                "consequence": {
                    "operation": operation,
                    "object_id": str(object_row.object_id),
                    **dict(details),
                }
            },
            metadata={
                "surface": "durable_object_command",
                "actor_id": context.actor_id,
            },
            idempotency_key=structural_event_idempotency_key(operation, idempotency_key),
            skip_graph_extraction=True,
            skip_projection=True,
            preserve_event_type=True,
            defer_commit=True,
        ),
    )
    if provenance_event:
        object_row.provenance_event_id = event_receipt.event_id
    db.flush()
    db.refresh(object_row)
    after = durable_object_payload(object_row)
    receipt = ConsequenceReceipt(
        actor_id=context.actor_id,
        session_id=context.session_id,
        idempotency_key=idempotency_key,
        operation=operation,
        object_id=str(object_row.object_id),
        world_event_id=event_receipt.event_id,
        payload_json={
            "before": dict(before) if before is not None else None,
            "after": after,
            "details": dict(details),
        },
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return _result_from_receipt(receipt, replayed=False)


def _recover_duplicate(
    db: Session,
    *,
    context: ActorContext,
    idempotency_key: str,
    operation: str,
    object_id: str | None = None,
) -> ConsequenceResult:
    db.rollback()
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=idempotency_key,
        operation=operation,
        object_id=object_id,
    )
    if existing is None:
        raise ConsequenceDomainError(
            "transaction_conflict",
            "The consequence command conflicted with another write and was not applied.",
        )
    return _result_from_receipt(existing, replayed=True)


def found_durable_object(
    db: Session,
    *,
    session_id: str,
    idempotency_key: str,
    name: str,
    description: str,
    object_kind: str,
    provenance_ref: str,
    properties: Mapping[str, Any] | None = None,
) -> ConsequenceResult:
    """Create one shard-founded object for seeding and later recipe output.

    This function is intentionally not exposed as an HTTP route. Ordinary prose
    and freeform action deltas cannot call it.
    """

    _require_capabilities(GameCapability.DURABLE_OBJECTS, GameCapability.CUSTODY)
    context = _actor_context(db, session_id)
    key = _idempotency_key(idempotency_key)
    existing = _existing_receipt(db, actor_id=context.actor_id, idempotency_key=key, operation="object_founded")
    if existing is not None:
        return _result_from_receipt(existing, replayed=True)

    safe_name = str(name or "").strip()
    safe_kind = str(object_kind or "").strip()
    safe_ref = str(provenance_ref or "").strip()
    if not safe_name or len(safe_name) > 120:
        raise ConsequenceDomainError("invalid_object_name", "Object name must contain 1 to 120 characters.", status_code=422)
    if not safe_kind or len(safe_kind) > 80:
        raise ConsequenceDomainError("invalid_object_kind", "Object kind must contain 1 to 80 characters.", status_code=422)
    if not safe_ref or len(safe_ref) > 120:
        raise ConsequenceDomainError("invalid_provenance", "A bounded provenance reference is required.", status_code=422)

    object_row = DurableObject(
        object_id=str(uuid.uuid4()),
        name=safe_name,
        description=str(description or "").strip()[:2000],
        object_kind=safe_kind,
        status="active",
        custodian_actor_id=context.actor_id,
        location=None,
        origin_shard_id=current_shard_id(),
        created_by_actor_id=context.actor_id,
        provenance_kind="shard_founding",
        provenance_ref=safe_ref,
        properties_json=dict(properties or {}),
        revision=1,
    )
    db.add(object_row)
    try:
        return _complete_consequence(
            db,
            context=context,
            idempotency_key=key,
            operation="object_founded",
            object_row=object_row,
            before=None,
            summary=f"{safe_name} becomes a durable part of this shard.",
            details={"to_actor_id": context.actor_id, "provenance_ref": safe_ref},
            provenance_event=True,
        )
    except IntegrityError:
        return _recover_duplicate(
            db,
            context=context,
            idempotency_key=key,
            operation="object_founded",
        )
    except Exception:
        db.rollback()
        raise


def place_durable_object(
    db: Session,
    *,
    session_id: str,
    object_id: str,
    idempotency_key: str,
) -> ConsequenceResult:
    _require_capabilities(GameCapability.DURABLE_OBJECTS, GameCapability.CUSTODY, GameCapability.PLACEMENT)
    context = _actor_context(db, session_id)
    key = _idempotency_key(idempotency_key)
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=key,
        operation="object_placed",
        object_id=object_id,
    )
    if existing is not None:
        return _result_from_receipt(existing, replayed=True)

    try:
        object_row = _locked_object(db, object_id)
        existing = _existing_receipt(
            db,
            actor_id=context.actor_id,
            idempotency_key=key,
            operation="object_placed",
            object_id=object_id,
        )
        if existing is not None:
            return _result_from_receipt(existing, replayed=True)
        if object_row.custodian_actor_id != context.actor_id:
            raise ConsequenceDomainError("not_custodian", "Only the current custodian can place this object.", status_code=403)
        before = durable_object_payload(object_row)
        object_row.custodian_actor_id = None
        object_row.location = context.location
        object_row.placed_by_actor_id = context.actor_id
        object_row.revision = int(object_row.revision or 1) + 1
        return _complete_consequence(
            db,
            context=context,
            idempotency_key=key,
            operation="object_placed",
            object_row=object_row,
            before=before,
            summary=f"{object_row.name} is placed at {context.location}.",
            details={"from_actor_id": context.actor_id, "to_location": context.location},
        )
    except IntegrityError:
        return _recover_duplicate(
            db,
            context=context,
            idempotency_key=key,
            operation="object_placed",
            object_id=object_id,
        )
    except Exception:
        db.rollback()
        raise


def pick_up_durable_object(
    db: Session,
    *,
    session_id: str,
    object_id: str,
    idempotency_key: str,
) -> ConsequenceResult:
    """Return an ordinarily placed object to the actor who put it down."""

    _require_capabilities(GameCapability.DURABLE_OBJECTS, GameCapability.CUSTODY, GameCapability.PLACEMENT)
    context = _actor_context(db, session_id)
    key = _idempotency_key(idempotency_key)
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=key,
        operation="object_picked_up",
        object_id=object_id,
    )
    if existing is not None:
        return _result_from_receipt(existing, replayed=True)

    try:
        object_row = _locked_object(db, object_id)
        existing = _existing_receipt(
            db,
            actor_id=context.actor_id,
            idempotency_key=key,
            operation="object_picked_up",
            object_id=object_id,
        )
        if existing is not None:
            return _result_from_receipt(existing, replayed=True)
        if object_row.custodian_actor_id is not None or object_row.location != context.location:
            raise ConsequenceDomainError("object_not_here", "That placed object is not at your exact location.", status_code=404)
        if object_row.placed_by_actor_id != context.actor_id:
            raise ConsequenceDomainError(
                "not_placer",
                "Only the actor who placed this object can pick it back up.",
                status_code=403,
            )
        before = durable_object_payload(object_row)
        object_row.custodian_actor_id = context.actor_id
        object_row.location = None
        object_row.placed_by_actor_id = None
        object_row.revision = int(object_row.revision or 1) + 1
        return _complete_consequence(
            db,
            context=context,
            idempotency_key=key,
            operation="object_picked_up",
            object_row=object_row,
            before=before,
            summary=f"{object_row.name} is picked up at {context.location}.",
            details={"from_location": context.location, "to_actor_id": context.actor_id},
        )
    except IntegrityError:
        return _recover_duplicate(
            db,
            context=context,
            idempotency_key=key,
            operation="object_picked_up",
            object_id=object_id,
        )
    except Exception:
        db.rollback()
        raise


def give_durable_object(
    db: Session,
    *,
    session_id: str,
    recipient_session_id: str,
    object_id: str,
    idempotency_key: str,
) -> ConsequenceResult:
    _require_capabilities(GameCapability.DURABLE_OBJECTS, GameCapability.CUSTODY, GameCapability.ATOMIC_GIVING)
    context = _actor_context(db, session_id)
    recipient = _actor_context(db, recipient_session_id)
    key = _idempotency_key(idempotency_key)
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=key,
        operation="object_given",
        object_id=object_id,
    )
    if existing is not None:
        return _result_from_receipt(existing, replayed=True)
    if recipient.actor_id == context.actor_id:
        raise ConsequenceDomainError("same_actor", "An actor cannot give an object to themself.", status_code=422)
    if recipient.location != context.location:
        raise ConsequenceDomainError("recipient_not_present", "The recipient must be at the same exact location.")

    try:
        object_row = _locked_object(db, object_id)
        existing = _existing_receipt(
            db,
            actor_id=context.actor_id,
            idempotency_key=key,
            operation="object_given",
            object_id=object_id,
        )
        if existing is not None:
            return _result_from_receipt(existing, replayed=True)
        if object_row.custodian_actor_id != context.actor_id:
            raise ConsequenceDomainError("not_custodian", "Only the current custodian can give this object.", status_code=403)
        before = durable_object_payload(object_row)
        object_row.custodian_actor_id = recipient.actor_id
        object_row.location = None
        object_row.placed_by_actor_id = None
        object_row.revision = int(object_row.revision or 1) + 1
        return _complete_consequence(
            db,
            context=context,
            idempotency_key=key,
            operation="object_given",
            object_row=object_row,
            before=before,
            summary=f"{object_row.name} changes hands.",
            details={
                "from_actor_id": context.actor_id,
                "to_actor_id": recipient.actor_id,
                "location": context.location,
            },
        )
    except IntegrityError:
        return _recover_duplicate(
            db,
            context=context,
            idempotency_key=key,
            operation="object_given",
            object_id=object_id,
        )
    except Exception:
        db.rollback()
        raise


def visible_durable_objects(db: Session, *, session_id: str) -> list[dict[str, Any]]:
    _require_capabilities(GameCapability.DURABLE_OBJECTS)
    context = _actor_context(db, session_id)
    # A stoop is the object's one active interaction surface while its entry is
    # open. The durable object still carries a physical location so the stoop
    # service can enforce exact-place take/withdraw rules, but it must not also
    # appear as an ordinary loose object at that location.
    active_stoop_object_ids = db.query(StoopObjectEntry.object_id).filter(StoopObjectEntry.status == "active")
    rows = (
        db.query(DurableObject)
        .filter(
            DurableObject.status == "active",
            ~DurableObject.object_id.in_(active_stoop_object_ids),
            or_(
                DurableObject.custodian_actor_id == context.actor_id,
                DurableObject.location == context.location,
            ),
        )
        .order_by(DurableObject.created_at.asc(), DurableObject.object_id.asc())
        .all()
    )
    return [
        {
            **durable_object_payload(row),
            "relation": "carried" if row.custodian_actor_id == context.actor_id else "here",
            "can_pick_up": bool(row.custodian_actor_id is None and row.location == context.location and row.placed_by_actor_id == context.actor_id),
        }
        for row in rows
    ]


def inspect_durable_object(db: Session, *, session_id: str, object_id: str) -> dict[str, Any]:
    objects = visible_durable_objects(db, session_id=session_id)
    for payload in objects:
        if payload["object_id"] == str(object_id or "").strip():
            return payload
    raise ConsequenceDomainError("object_not_visible", "That object is not carried or present here.", status_code=404)
