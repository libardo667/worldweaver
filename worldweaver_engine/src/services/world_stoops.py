# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Bounded exact-location stoops for voluntarily shared durable objects."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    DurableObject,
    StoopObjectEntry,
    StoopReceipt,
    WorldNode,
    WorldStoop,
)
from .consequence_objects import (
    ActorContext,
    ConsequenceDomainError,
    consequence_actor_context,
    consequence_idempotency_key,
    durable_object_payload,
    require_consequence_capabilities,
)
from .event_submission import (
    WorldEventCommand,
    structural_event_idempotency_key,
    submit_world_event,
)
from .shard_experience import GameCapability

_STOOP_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _require_stoop_capabilities() -> None:
    require_consequence_capabilities(
        GameCapability.DURABLE_OBJECTS,
        GameCapability.CUSTODY,
        GameCapability.PLACEMENT,
        GameCapability.STOOPS,
    )


def _known_exact_place(db: Session, location: str) -> bool:
    return (
        db.query(WorldNode.id)
        .filter(
            WorldNode.name == location,
            WorldNode.node_type.in_(("location", "landmark", "sublocation")),
        )
        .first()
        is not None
    )


def found_world_stoop(
    db: Session,
    *,
    stoop_id: str,
    title: str,
    prompt: str,
    location: str,
    capacity: int,
) -> WorldStoop:
    """Trusted town setup hook; gameplay cannot claim arbitrary stoops."""

    _require_stoop_capabilities()
    safe_id = str(stoop_id or "").strip()
    safe_title = str(title or "").strip()
    safe_prompt = str(prompt or "").strip()
    safe_location = str(location or "").strip()
    if not _STOOP_ID_RE.fullmatch(safe_id) or len(safe_id) > 80:
        raise ConsequenceDomainError(
            "invalid_stoop_id",
            "Stoop ID must be a bounded lowercase identifier.",
            status_code=422,
        )
    if not safe_title or len(safe_title) > 120:
        raise ConsequenceDomainError(
            "invalid_stoop_title",
            "Stoop title must contain 1 to 120 characters.",
            status_code=422,
        )
    if len(safe_prompt) > 500:
        raise ConsequenceDomainError(
            "invalid_stoop_prompt",
            "Stoop prompt cannot exceed 500 characters.",
            status_code=422,
        )
    if (
        not safe_location
        or len(safe_location) > 200
        or not _known_exact_place(db, safe_location)
    ):
        raise ConsequenceDomainError(
            "stoop_location_not_found",
            "The stoop's exact place does not exist.",
            status_code=404,
        )
    if not 1 <= int(capacity) <= 50:
        raise ConsequenceDomainError(
            "invalid_stoop_capacity",
            "Stoop capacity must be between 1 and 50.",
            status_code=422,
        )
    existing = db.get(WorldStoop, safe_id)
    if existing is not None:
        expected = (safe_title, safe_prompt, safe_location, int(capacity))
        current = (
            str(existing.title),
            str(existing.prompt or ""),
            str(existing.location),
            int(existing.capacity),
        )
        if current != expected:
            raise ConsequenceDomainError(
                "stoop_already_exists", "That stoop ID already names different setup."
            )
        return existing
    row = WorldStoop(
        stoop_id=safe_id,
        title=safe_title,
        prompt=safe_prompt,
        location=safe_location,
        capacity=int(capacity),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _stoop(db: Session, stoop_id: str, *, lock: bool = False) -> WorldStoop:
    safe_id = str(stoop_id or "").strip()
    query = db.query(WorldStoop).filter(WorldStoop.stoop_id == safe_id)
    if lock:
        query = query.with_for_update()
    row = query.one_or_none()
    if row is None:
        raise ConsequenceDomainError(
            "stoop_not_found", "World stoop not found.", status_code=404
        )
    return row


def _entry(db: Session, entry_id: str, *, lock: bool = False) -> StoopObjectEntry:
    safe_id = str(entry_id or "").strip()
    query = db.query(StoopObjectEntry).filter(StoopObjectEntry.entry_id == safe_id)
    if lock:
        query = query.with_for_update()
    row = query.one_or_none()
    if row is None:
        raise ConsequenceDomainError(
            "stoop_entry_not_found", "Stoop entry not found.", status_code=404
        )
    return row


def _object(db: Session, object_id: str, *, lock: bool = False) -> DurableObject:
    query = db.query(DurableObject).filter(
        DurableObject.object_id == str(object_id or "").strip(),
        DurableObject.status == "active",
    )
    if lock:
        query = query.with_for_update()
    row = query.one_or_none()
    if row is None:
        raise ConsequenceDomainError(
            "object_not_found", "Durable object not found.", status_code=404
        )
    return row


def _public_object(row: DurableObject) -> dict[str, Any]:
    payload = durable_object_payload(row)
    provenance = dict(payload.get("provenance") or {})
    provenance.pop("created_by_actor_id", None)
    payload["provenance"] = provenance
    return payload


def _active_count(db: Session, stoop_id: str) -> int:
    return int(
        db.query(StoopObjectEntry)
        .filter(
            StoopObjectEntry.stoop_id == stoop_id,
            StoopObjectEntry.status == "active",
        )
        .count()
    )


def _stoop_payload(row: WorldStoop, *, active_count: int) -> dict[str, Any]:
    return {
        "stoop_id": str(row.stoop_id),
        "title": str(row.title),
        "prompt": str(row.prompt or ""),
        "location": str(row.location),
        "capacity": int(row.capacity),
        "active_count": int(active_count),
        "space_remaining": max(0, int(row.capacity) - int(active_count)),
    }


def _entry_payload(
    row: StoopObjectEntry,
    *,
    object_row: DurableObject,
    viewer_actor_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "entry_id": str(row.entry_id),
        "stoop_id": str(row.stoop_id),
        "status": str(row.status),
        "object": _public_object(object_row),
        "object_revision_at_leave": int(row.object_revision_at_leave),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }
    if viewer_actor_id is not None:
        depositor = viewer_actor_id == row.left_by_actor_id
        payload.update(
            {
                "can_take": bool(row.status == "active" and not depositor),
                "can_withdraw": bool(row.status == "active" and depositor),
            }
        )
    return payload


def _stoops_at_location(db: Session, location: str) -> dict[str, Any]:
    rows = (
        db.query(WorldStoop)
        .filter(WorldStoop.location == location)
        .order_by(WorldStoop.title.asc())
        .all()
    )
    stoops = [
        _stoop_payload(row, active_count=_active_count(db, str(row.stoop_id)))
        for row in rows
    ]
    return {"location": location, "stoops": stoops, "count": len(stoops)}


def _browse_stoop_at_location(
    db: Session, stoop_id: str, location: str, viewer_actor_id: str | None
) -> dict[str, Any]:
    stoop = _stoop(db, stoop_id)
    if stoop.location != location:
        raise ConsequenceDomainError(
            "stoop_not_here",
            "You must be at the stoop's exact place to browse it.",
            status_code=403,
        )
    rows = (
        db.query(StoopObjectEntry)
        .filter(
            StoopObjectEntry.stoop_id == stoop.stoop_id,
            StoopObjectEntry.status == "active",
        )
        .order_by(StoopObjectEntry.created_at.desc(), StoopObjectEntry.entry_id.desc())
        .limit(int(stoop.capacity))
        .all()
    )
    entries = [
        _entry_payload(
            row,
            object_row=_object(db, str(row.object_id)),
            viewer_actor_id=viewer_actor_id,
        )
        for row in rows
    ]
    return {
        "stoop": _stoop_payload(stoop, active_count=len(rows)),
        "entries": entries,
        "count": len(entries),
    }


def local_stoops(db: Session, *, session_id: str) -> dict[str, Any]:
    """List nearby stoop shells without exposing their contents."""

    _require_stoop_capabilities()
    context = consequence_actor_context(db, session_id)
    return _stoops_at_location(db, context.location)


def local_stoops_at(db: Session, *, location: str) -> dict[str, Any]:
    """List a place's stoop shells for a sessionless public onlooker."""

    _require_stoop_capabilities()
    safe_location = str(location or "").strip()
    if not safe_location:
        raise ConsequenceDomainError(
            "location_required",
            "A location is required to look at stoops.",
            status_code=400,
        )
    return _stoops_at_location(db, safe_location)


def browse_world_stoop(
    db: Session, *, session_id: str, stoop_id: str
) -> dict[str, Any]:
    """Electively browse one stoop only while physically at its exact place."""

    _require_stoop_capabilities()
    context = consequence_actor_context(db, session_id)
    return _browse_stoop_at_location(db, stoop_id, context.location, context.actor_id)


def browse_world_stoop_at(
    db: Session, *, location: str, stoop_id: str
) -> dict[str, Any]:
    """Electively browse one stoop as a sessionless onlooker viewing its place.

    Entries carry no take/withdraw affordances — looking is not holding.
    """

    _require_stoop_capabilities()
    safe_location = str(location or "").strip()
    if not safe_location:
        raise ConsequenceDomainError(
            "location_required",
            "A location is required to browse a stoop.",
            status_code=400,
        )
    return _browse_stoop_at_location(db, stoop_id, safe_location, None)


def _existing_receipt(
    db: Session,
    *,
    actor_id: str,
    key: str,
    operation: str,
    entry_id: str | None = None,
) -> StoopReceipt | None:
    row = (
        db.query(StoopReceipt)
        .filter(
            StoopReceipt.actor_id == actor_id,
            StoopReceipt.idempotency_key == key,
        )
        .one_or_none()
    )
    if row is None:
        return None
    if row.operation != operation or (
        entry_id is not None and row.entry_id != entry_id
    ):
        raise ConsequenceDomainError(
            "idempotency_conflict",
            "That retry key was already used for a different stoop command.",
        )
    return row


def _receipt_payload(row: StoopReceipt, *, replayed: bool) -> dict[str, Any]:
    payload = dict(row.payload_json or {})
    return {
        "ok": True,
        "replayed": replayed,
        "stoop": dict(payload.get("stoop") or {}),
        "entry": dict(payload.get("entry") or {}),
        "receipt": {
            "receipt_id": str(row.receipt_id),
            "operation": str(row.operation),
            "entry_id": str(row.entry_id),
            "world_event_id": int(row.world_event_id),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        },
    }


def _finish(
    db: Session,
    *,
    context: ActorContext,
    key: str,
    operation: str,
    entry: StoopObjectEntry,
    stoop_payload: dict[str, Any],
    entry_payload: dict[str, Any],
    summary: str,
) -> dict[str, Any]:
    event = submit_world_event(
        db,
        WorldEventCommand(
            session_id=context.session_id,
            event_type=operation,
            summary=summary,
            delta={"stoop_object": {"stoop": stoop_payload, "entry": entry_payload}},
            metadata={"surface": "world_stoop_command", "actor_id": context.actor_id},
            idempotency_key=structural_event_idempotency_key(operation, key),
            skip_graph_extraction=True,
            skip_projection=True,
            preserve_event_type=True,
            defer_commit=True,
        ),
    )
    receipt = StoopReceipt(
        actor_id=context.actor_id,
        session_id=context.session_id,
        idempotency_key=key,
        operation=operation,
        entry_id=str(entry.entry_id),
        world_event_id=event.event_id,
        payload_json={"stoop": stoop_payload, "entry": entry_payload},
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return _receipt_payload(receipt, replayed=False)


def _recover_duplicate(
    db: Session,
    *,
    context: ActorContext,
    key: str,
    operation: str,
    entry_id: str | None = None,
) -> dict[str, Any]:
    db.rollback()
    row = _existing_receipt(
        db,
        actor_id=context.actor_id,
        key=key,
        operation=operation,
        entry_id=entry_id,
    )
    if row is None:
        raise ConsequenceDomainError(
            "transaction_conflict", "The stoop command conflicted and was not applied."
        )
    return _receipt_payload(row, replayed=True)


def leave_object_on_stoop(
    db: Session,
    *,
    session_id: str,
    stoop_id: str,
    object_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    """Voluntarily make one held object available to any later visitor."""

    _require_stoop_capabilities()
    context = consequence_actor_context(db, session_id)
    key = consequence_idempotency_key(idempotency_key)
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        key=key,
        operation="stoop_object_left",
    )
    if existing is not None:
        return _receipt_payload(existing, replayed=True)
    try:
        stoop = _stoop(db, stoop_id, lock=True)
        if stoop.location != context.location:
            raise ConsequenceDomainError(
                "stoop_not_here",
                "You must be at the stoop's exact place to leave an object.",
                status_code=403,
            )
        active_count = _active_count(db, str(stoop.stoop_id))
        if active_count >= int(stoop.capacity):
            raise ConsequenceDomainError(
                "stoop_full",
                "This single-instance stoop is full. Take or withdraw something before leaving another object.",
            )
        object_row = _object(db, object_id, lock=True)
        if object_row.custodian_actor_id != context.actor_id:
            raise ConsequenceDomainError(
                "not_custodian",
                "Only the current custodian can leave this object.",
                status_code=403,
            )
        active_entry = (
            db.query(StoopObjectEntry)
            .filter(
                StoopObjectEntry.object_id == object_row.object_id,
                StoopObjectEntry.status == "active",
            )
            .one_or_none()
        )
        if active_entry is not None:
            raise ConsequenceDomainError(
                "object_already_on_stoop", "That object is already active on a stoop."
            )
        object_row.custodian_actor_id = None
        object_row.location = str(stoop.location)
        object_row.placed_by_actor_id = None
        object_row.revision = int(object_row.revision or 1) + 1
        entry = StoopObjectEntry(
            stoop_id=str(stoop.stoop_id),
            object_id=str(object_row.object_id),
            left_by_actor_id=context.actor_id,
            status="active",
            object_revision_at_leave=int(object_row.revision),
        )
        db.add(entry)
        db.flush()
        stoop_payload = _stoop_payload(stoop, active_count=active_count + 1)
        entry_payload = _entry_payload(
            entry, object_row=object_row, viewer_actor_id=context.actor_id
        )
        return _finish(
            db,
            context=context,
            key=key,
            operation="stoop_object_left",
            entry=entry,
            stoop_payload=stoop_payload,
            entry_payload=entry_payload,
            summary=f"{object_row.name} is left on {stoop.title} for someone to take.",
        )
    except IntegrityError:
        return _recover_duplicate(
            db,
            context=context,
            key=key,
            operation="stoop_object_left",
        )
    except Exception:
        db.rollback()
        raise


def _resolve_stoop_entry(
    db: Session,
    *,
    session_id: str,
    entry_id: str,
    idempotency_key: str,
    resolution: str,
) -> dict[str, Any]:
    _require_stoop_capabilities()
    context = consequence_actor_context(db, session_id)
    key = consequence_idempotency_key(idempotency_key)
    safe_entry_id = str(entry_id or "").strip()
    operation = (
        "stoop_object_taken" if resolution == "taken" else "stoop_object_withdrawn"
    )
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        key=key,
        operation=operation,
        entry_id=safe_entry_id,
    )
    if existing is not None:
        return _receipt_payload(existing, replayed=True)
    try:
        entry = _entry(db, safe_entry_id, lock=True)
        if entry.status != "active":
            raise ConsequenceDomainError(
                "stoop_entry_not_active", "That stoop entry is no longer available."
            )
        stoop = _stoop(db, str(entry.stoop_id), lock=True)
        if stoop.location != context.location:
            raise ConsequenceDomainError(
                "stoop_not_here",
                "You must be at the stoop's exact place to move this object.",
                status_code=403,
            )
        if resolution == "taken" and entry.left_by_actor_id == context.actor_id:
            raise ConsequenceDomainError(
                "use_stoop_withdraw",
                "The depositor should withdraw their own object instead of taking it.",
                status_code=422,
            )
        if resolution == "withdrawn" and entry.left_by_actor_id != context.actor_id:
            raise ConsequenceDomainError(
                "not_stoop_depositor",
                "Only the depositor can withdraw this object.",
                status_code=403,
            )
        object_row = _object(db, str(entry.object_id), lock=True)
        if (
            object_row.custodian_actor_id is not None
            or object_row.location != stoop.location
        ):
            raise ConsequenceDomainError(
                "stoop_object_mismatch",
                "The stoop entry and object attachment no longer agree.",
            )
        object_row.custodian_actor_id = context.actor_id
        object_row.location = None
        object_row.placed_by_actor_id = None
        object_row.revision = int(object_row.revision or 1) + 1
        entry.status = resolution
        entry.taken_by_actor_id = context.actor_id if resolution == "taken" else None
        entry.resolved_at = _utcnow()
        db.flush()
        active_count = _active_count(db, str(stoop.stoop_id))
        stoop_payload = _stoop_payload(stoop, active_count=active_count)
        entry_payload = _entry_payload(
            entry, object_row=object_row, viewer_actor_id=context.actor_id
        )
        verb = "taken from" if resolution == "taken" else "withdrawn from"
        return _finish(
            db,
            context=context,
            key=key,
            operation=operation,
            entry=entry,
            stoop_payload=stoop_payload,
            entry_payload=entry_payload,
            summary=f"{object_row.name} is {verb} {stoop.title}.",
        )
    except IntegrityError:
        return _recover_duplicate(
            db,
            context=context,
            key=key,
            operation=operation,
            entry_id=safe_entry_id,
        )
    except Exception:
        db.rollback()
        raise


def take_stoop_object(
    db: Session,
    *,
    session_id: str,
    entry_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    return _resolve_stoop_entry(
        db,
        session_id=session_id,
        entry_id=entry_id,
        idempotency_key=idempotency_key,
        resolution="taken",
    )


def withdraw_stoop_object(
    db: Session,
    *,
    session_id: str,
    entry_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    return _resolve_stoop_entry(
        db,
        session_id=session_id,
        entry_id=entry_id,
        idempotency_key=idempotency_key,
        resolution="withdrawn",
    )
