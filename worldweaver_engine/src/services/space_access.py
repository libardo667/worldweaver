# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Actor-scoped entry rules for exact places on an opted-in game shard.

These rules are deliberately checked only for destinations. They can refuse
entry, but they cannot keep a person inside a place or block shard travel back
to a hearth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    SessionVars,
    SpaceAccessGrant,
    SpaceAccessPolicy,
    SpaceAccessReceipt,
    SpaceAccessRequest,
    WorldNode,
)
from .event_submission import WorldEventCommand, structural_event_idempotency_key, submit_world_event
from .shard_experience import (
    GameCapability,
    GameCapabilityUnavailable,
    configured_game_declaration,
    require_game_capabilities,
)

AccessMode = Literal["public", "requestable", "private", "closed"]
RequestDecision = Literal["admitted", "denied"]

_MODES = frozenset({"public", "requestable", "private", "closed"})
_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class SpaceAccessError(ValueError):
    """A safe, typed failure from the space-access boundary."""

    def __init__(self, code: str, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class ActorContext:
    session_id: str
    actor_id: str
    location: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _variables(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    nested = raw.get("variables")
    if raw.get("_v") == 2 and isinstance(nested, dict):
        return dict(nested)
    return dict(raw)


def _actor_context(db: Session, session_id: str) -> ActorContext:
    normalized = str(session_id or "").strip()
    if not _SESSION_RE.fullmatch(normalized):
        raise SpaceAccessError("invalid_session", "Invalid session ID.", status_code=422)
    row = db.get(SessionVars, normalized)
    if row is None:
        raise SpaceAccessError("session_not_found", "Session not found.", status_code=404)
    actor_id = str(row.actor_id or "").strip()
    if not actor_id:
        raise SpaceAccessError("actor_identity_required", "Session has no stable actor identity.")
    return ActorContext(
        session_id=normalized,
        actor_id=actor_id,
        location=str(_variables(row.vars).get("location") or "").strip(),
    )


def _recipient_actor_id(db: Session, session_id: str) -> str:
    return _actor_context(db, session_id).actor_id


def _idempotency_key(value: str) -> str:
    normalized = str(value or "").strip()
    if not _IDEMPOTENCY_RE.fullmatch(normalized):
        raise SpaceAccessError(
            "invalid_idempotency_key",
            "Idempotency key must use only letters, digits, dot, underscore, colon, or hyphen.",
            status_code=422,
        )
    return normalized


def _require_space_permissions() -> None:
    try:
        require_game_capabilities(GameCapability.SPACE_PERMISSIONS)
    except GameCapabilityUnavailable as exc:
        raise SpaceAccessError("game_capability_unavailable", str(exc), status_code=403) from exc


def space_permissions_enabled() -> bool:
    """Return whether destination checks should apply on this process."""

    declaration = configured_game_declaration()
    return bool(declaration and GameCapability.SPACE_PERMISSIONS in declaration.capabilities)


def _normalize_location(value: str) -> str:
    location = str(value or "").strip()
    if not location or len(location) > 200:
        raise SpaceAccessError("invalid_location", "Location must contain 1 to 200 characters.", status_code=422)
    return location


def _require_known_place(db: Session, location: str) -> None:
    exists = (
        db.query(WorldNode.id)
        .filter(
            WorldNode.name == location,
            WorldNode.node_type.in_(("location", "landmark", "sublocation")),
        )
        .first()
    )
    if exists is None:
        raise SpaceAccessError("location_not_found", "That exact place does not exist.", status_code=404)


def _policy(db: Session, location: str, *, lock: bool = False) -> SpaceAccessPolicy:
    query = db.query(SpaceAccessPolicy).filter(SpaceAccessPolicy.location == location)
    if lock:
        query = query.with_for_update()
    row = query.one_or_none()
    if row is None:
        raise SpaceAccessError("space_not_controlled", "That place has no access rule.", status_code=404)
    return row


def _active_grant(db: Session, *, location: str, actor_id: str) -> SpaceAccessGrant | None:
    return (
        db.query(SpaceAccessGrant)
        .filter(
            SpaceAccessGrant.location == location,
            SpaceAccessGrant.actor_id == actor_id,
            SpaceAccessGrant.active.is_(True),
        )
        .one_or_none()
    )


def _policy_payload(row: SpaceAccessPolicy, *, actor_id: str, admitted: bool) -> dict[str, Any]:
    is_controller = str(row.controller_actor_id) == actor_id
    mode = str(row.mode)
    if mode == "public":
        can_enter, reason = True, "public"
    elif mode == "closed":
        can_enter, reason = False, "closed"
    elif is_controller:
        can_enter, reason = True, "controller"
    elif admitted:
        can_enter, reason = True, "admitted"
    else:
        can_enter, reason = False, "permission_required"
    return {
        "location": str(row.location),
        "mode": mode,
        "note": str(row.note or ""),
        "revision": int(row.revision or 1),
        "is_controller": is_controller,
        "admitted": admitted,
        "can_enter": can_enter,
        "can_request": mode == "requestable" and not can_enter,
        "entry_reason": reason,
    }


def access_status(db: Session, *, session_id: str, location: str) -> dict[str, Any]:
    """Return only the caller's relationship to one exact destination."""

    _require_space_permissions()
    context = _actor_context(db, session_id)
    normalized = _normalize_location(location)
    row = db.get(SpaceAccessPolicy, normalized)
    if row is None:
        return {
            "location": normalized,
            "mode": "public",
            "note": "",
            "revision": 0,
            "is_controller": False,
            "admitted": False,
            "can_enter": True,
            "can_request": False,
            "entry_reason": "no_restriction",
            "active_grants": [],
        }
    admitted = _active_grant(db, location=normalized, actor_id=context.actor_id) is not None
    payload = _policy_payload(row, actor_id=context.actor_id, admitted=admitted)
    payload["active_grants"] = []
    if payload["is_controller"]:
        grants = (
            db.query(SpaceAccessGrant)
            .filter(
                SpaceAccessGrant.location == normalized,
                SpaceAccessGrant.active.is_(True),
            )
            .order_by(SpaceAccessGrant.actor_id.asc())
            .all()
        )
        for grant in grants:
            session = db.query(SessionVars).filter(SessionVars.actor_id == grant.actor_id).order_by(SessionVars.session_id.asc()).first()
            payload["active_grants"].append(
                {
                    "actor_id": str(grant.actor_id),
                    "session_id": str(session.session_id) if session is not None else "",
                }
            )
    return payload


def assert_route_entry_allowed(db: Session, *, session_id: str, destinations: list[str]) -> None:
    """Reject the first protected destination before movement mutates state.

    Ordinary shards and places without a policy remain public. The origin is
    intentionally not accepted here, so this function cannot prevent exit.
    """

    if not space_permissions_enabled():
        return
    context = _actor_context(db, session_id)
    seen: set[str] = set()
    for raw_location in destinations:
        location = str(raw_location or "").strip()
        if not location or location in seen:
            continue
        seen.add(location)
        row = db.get(SpaceAccessPolicy, location)
        if row is None:
            continue
        admitted = _active_grant(db, location=location, actor_id=context.actor_id) is not None
        status = _policy_payload(row, actor_id=context.actor_id, admitted=admitted)
        if not status["can_enter"]:
            code = "space_closed" if status["entry_reason"] == "closed" else "space_access_required"
            message = f"{location} is closed to new entry." if code == "space_closed" else f"You need permission to enter {location}."
            raise SpaceAccessError(code, message, status_code=403)


def found_space_policy(
    db: Session,
    *,
    location: str,
    controller_actor_id: str,
    mode: AccessMode = "private",
    note: str = "",
) -> SpaceAccessPolicy:
    """Trusted town setup hook; gameplay has no public policy-founding route."""

    _require_space_permissions()
    normalized = _normalize_location(location)
    normalized_mode = str(mode or "").strip()
    if normalized_mode not in _MODES:
        raise SpaceAccessError("invalid_mode", "Unknown access mode.", status_code=422)
    actor_id = str(controller_actor_id or "").strip()
    if not actor_id or len(actor_id) > 36:
        raise SpaceAccessError("invalid_controller", "A stable controller actor ID is required.", status_code=422)
    _require_known_place(db, normalized)
    existing = db.get(SpaceAccessPolicy, normalized)
    if existing is not None:
        if existing.controller_actor_id != actor_id:
            raise SpaceAccessError("policy_already_exists", "That place already has a different controller.")
        return existing
    row = SpaceAccessPolicy(
        location=normalized,
        mode=normalized_mode,
        controller_actor_id=actor_id,
        note=str(note or "").strip()[:500],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _existing_receipt(
    db: Session,
    *,
    actor_id: str,
    idempotency_key: str,
    operation: str,
    location: str,
) -> SpaceAccessReceipt | None:
    row = (
        db.query(SpaceAccessReceipt)
        .filter(
            SpaceAccessReceipt.actor_id == actor_id,
            SpaceAccessReceipt.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if row is None:
        return None
    if row.operation != operation or row.location != location:
        raise SpaceAccessError("idempotency_conflict", "That retry key was already used for a different access command.")
    return row


def _receipt_payload(row: SpaceAccessReceipt, *, replayed: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "replayed": replayed,
        "receipt": {
            "receipt_id": str(row.receipt_id),
            "operation": str(row.operation),
            "location": str(row.location),
            "world_event_id": int(row.world_event_id) if row.world_event_id is not None else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "result": dict(row.payload_json or {}),
        },
    }


def _record_receipt(
    db: Session,
    *,
    context: ActorContext,
    idempotency_key: str,
    operation: str,
    location: str,
    result: dict[str, Any],
    public_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    world_event_id: int | None = None
    if public_event is not None:
        event = submit_world_event(
            db,
            WorldEventCommand(
                session_id=context.session_id,
                event_type=operation,
                summary=str(public_event["summary"]),
                delta=dict(public_event["delta"]),
                metadata={"surface": "space_access_command"},
                idempotency_key=structural_event_idempotency_key(operation, idempotency_key),
                skip_graph_extraction=True,
                skip_projection=True,
                preserve_event_type=True,
                defer_commit=True,
            ),
        )
        world_event_id = event.event_id
    receipt = SpaceAccessReceipt(
        actor_id=context.actor_id,
        session_id=context.session_id,
        idempotency_key=idempotency_key,
        operation=operation,
        location=location,
        world_event_id=world_event_id,
        payload_json=result,
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return _receipt_payload(receipt, replayed=False)


def _begin_command(
    db: Session,
    *,
    session_id: str,
    idempotency_key: str,
    operation: str,
    location: str,
) -> tuple[ActorContext, str, str, dict[str, Any] | None]:
    _require_space_permissions()
    context = _actor_context(db, session_id)
    key = _idempotency_key(idempotency_key)
    normalized_location = _normalize_location(location)
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=key,
        operation=operation,
        location=normalized_location,
    )
    return context, key, normalized_location, (_receipt_payload(existing, replayed=True) if existing else None)


def _recover_duplicate(
    db: Session,
    *,
    context: ActorContext,
    idempotency_key: str,
    operation: str,
    location: str,
) -> dict[str, Any]:
    db.rollback()
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=idempotency_key,
        operation=operation,
        location=location,
    )
    if existing is None:
        raise SpaceAccessError("transaction_conflict", "The access command conflicted and was not applied.")
    return _receipt_payload(existing, replayed=True)


def set_space_mode(
    db: Session,
    *,
    session_id: str,
    location: str,
    mode: AccessMode,
    idempotency_key: str,
    note: str | None = None,
) -> dict[str, Any]:
    operation = "space_mode_changed"
    context, key, location, replay = _begin_command(
        db,
        session_id=session_id,
        idempotency_key=idempotency_key,
        operation=operation,
        location=location,
    )
    if replay:
        return replay
    normalized_mode = str(mode or "").strip()
    if normalized_mode not in _MODES:
        raise SpaceAccessError("invalid_mode", "Unknown access mode.", status_code=422)
    row = _policy(db, location, lock=True)
    if row.controller_actor_id != context.actor_id:
        raise SpaceAccessError("not_space_controller", "Only this place's controller can change its access rule.", status_code=403)
    if row.mode == normalized_mode and (note is None or row.note == str(note or "").strip()):
        raise SpaceAccessError("no_access_change", "That access rule is already in effect.")
    before = {"mode": str(row.mode), "note": str(row.note or ""), "revision": int(row.revision or 1)}
    row.mode = normalized_mode
    if note is not None:
        row.note = str(note or "").strip()[:500]
    row.revision = int(row.revision or 1) + 1
    db.flush()
    result = {
        "before": before,
        "after": {"mode": str(row.mode), "note": str(row.note or ""), "revision": int(row.revision)},
    }
    try:
        return _record_receipt(
            db,
            context=context,
            idempotency_key=key,
            operation=operation,
            location=location,
            result=result,
            public_event={
                "summary": f"Access at {location} changed from {before['mode']} to {row.mode}.",
                "delta": {
                    "space_access": {
                        "location": location,
                        "before_mode": before["mode"],
                        "after_mode": str(row.mode),
                        "revision": int(row.revision),
                    }
                },
            },
        )
    except IntegrityError:
        return _recover_duplicate(db, context=context, idempotency_key=key, operation=operation, location=location)


def request_space_access(
    db: Session,
    *,
    session_id: str,
    location: str,
    idempotency_key: str,
    note: str = "",
) -> dict[str, Any]:
    operation = "space_access_requested"
    context, key, location, replay = _begin_command(
        db,
        session_id=session_id,
        idempotency_key=idempotency_key,
        operation=operation,
        location=location,
    )
    if replay:
        return replay
    row = _policy(db, location, lock=True)
    status = _policy_payload(
        row,
        actor_id=context.actor_id,
        admitted=_active_grant(db, location=location, actor_id=context.actor_id) is not None,
    )
    if status["can_enter"]:
        raise SpaceAccessError("access_already_available", "You can already enter that place.")
    if row.mode != "requestable":
        raise SpaceAccessError("space_not_requestable", "That place is not accepting access requests.", status_code=403)
    pending = (
        db.query(SpaceAccessRequest)
        .filter(
            SpaceAccessRequest.location == location,
            SpaceAccessRequest.requester_actor_id == context.actor_id,
            SpaceAccessRequest.status == "pending",
        )
        .one_or_none()
    )
    if pending is not None:
        raise SpaceAccessError("request_already_pending", "You already have a pending request for that place.")
    request = SpaceAccessRequest(
        location=location,
        requester_actor_id=context.actor_id,
        requester_session_id=context.session_id,
        note=str(note or "").strip()[:500],
    )
    db.add(request)
    db.flush()
    result = {
        "request": {
            "request_id": str(request.request_id),
            "location": location,
            "status": "pending",
            "note": str(request.note or ""),
        }
    }
    try:
        return _record_receipt(
            db,
            context=context,
            idempotency_key=key,
            operation=operation,
            location=location,
            result=result,
        )
    except IntegrityError:
        return _recover_duplicate(db, context=context, idempotency_key=key, operation=operation, location=location)


def invite_to_space(
    db: Session,
    *,
    session_id: str,
    recipient_session_id: str,
    location: str,
    idempotency_key: str,
) -> dict[str, Any]:
    operation = "space_access_granted"
    context, key, location, replay = _begin_command(
        db,
        session_id=session_id,
        idempotency_key=idempotency_key,
        operation=operation,
        location=location,
    )
    if replay:
        return replay
    row = _policy(db, location, lock=True)
    if row.controller_actor_id != context.actor_id:
        raise SpaceAccessError("not_space_controller", "Only this place's controller can admit someone.", status_code=403)
    recipient_actor_id = _recipient_actor_id(db, recipient_session_id)
    if recipient_actor_id == context.actor_id:
        raise SpaceAccessError("controller_already_admitted", "The controller already has access.")
    grant = db.query(SpaceAccessGrant).filter(SpaceAccessGrant.location == location, SpaceAccessGrant.actor_id == recipient_actor_id).with_for_update().one_or_none()
    if grant is not None and grant.active:
        raise SpaceAccessError("actor_already_admitted", "That person is already admitted.")
    if grant is None:
        grant = SpaceAccessGrant(
            location=location,
            actor_id=recipient_actor_id,
            active=True,
            granted_by_actor_id=context.actor_id,
        )
        db.add(grant)
    else:
        grant.active = True
        grant.granted_by_actor_id = context.actor_id
        grant.revision = int(grant.revision or 1) + 1
    db.flush()
    result = {"grant": {"location": location, "actor_id": recipient_actor_id, "active": True}}
    try:
        return _record_receipt(
            db,
            context=context,
            idempotency_key=key,
            operation=operation,
            location=location,
            result=result,
        )
    except IntegrityError:
        return _recover_duplicate(db, context=context, idempotency_key=key, operation=operation, location=location)


def revoke_space_access(
    db: Session,
    *,
    session_id: str,
    recipient_session_id: str,
    location: str,
    idempotency_key: str,
) -> dict[str, Any]:
    operation = "space_access_revoked"
    context, key, location, replay = _begin_command(
        db,
        session_id=session_id,
        idempotency_key=idempotency_key,
        operation=operation,
        location=location,
    )
    if replay:
        return replay
    row = _policy(db, location, lock=True)
    if row.controller_actor_id != context.actor_id:
        raise SpaceAccessError("not_space_controller", "Only this place's controller can revoke access.", status_code=403)
    recipient_actor_id = _recipient_actor_id(db, recipient_session_id)
    grant = db.query(SpaceAccessGrant).filter(SpaceAccessGrant.location == location, SpaceAccessGrant.actor_id == recipient_actor_id).with_for_update().one_or_none()
    if grant is None or not grant.active:
        raise SpaceAccessError("active_grant_not_found", "That person does not have active access.", status_code=404)
    grant.active = False
    grant.revision = int(grant.revision or 1) + 1
    db.flush()
    result = {"grant": {"location": location, "actor_id": recipient_actor_id, "active": False}}
    try:
        return _record_receipt(
            db,
            context=context,
            idempotency_key=key,
            operation=operation,
            location=location,
            result=result,
        )
    except IntegrityError:
        return _recover_duplicate(db, context=context, idempotency_key=key, operation=operation, location=location)


def pending_requests(db: Session, *, session_id: str, location: str) -> dict[str, Any]:
    """Let a controller electively review only one controlled place's queue."""

    _require_space_permissions()
    context = _actor_context(db, session_id)
    normalized = _normalize_location(location)
    row = _policy(db, normalized)
    if row.controller_actor_id != context.actor_id:
        raise SpaceAccessError("not_space_controller", "Only this place's controller can review its requests.", status_code=403)
    requests = db.query(SpaceAccessRequest).filter(SpaceAccessRequest.location == normalized, SpaceAccessRequest.status == "pending").order_by(SpaceAccessRequest.created_at.asc(), SpaceAccessRequest.request_id.asc()).all()
    return {
        "location": normalized,
        "requests": [
            {
                "request_id": str(item.request_id),
                "requester_actor_id": str(item.requester_actor_id),
                "requester_session_id": str(item.requester_session_id),
                "note": str(item.note or ""),
                "status": str(item.status),
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in requests
        ],
        "count": len(requests),
    }


def resolve_access_request(
    db: Session,
    *,
    session_id: str,
    request_id: str,
    decision: RequestDecision,
    idempotency_key: str,
) -> dict[str, Any]:
    _require_space_permissions()
    context = _actor_context(db, session_id)
    request = db.query(SpaceAccessRequest).filter(SpaceAccessRequest.request_id == str(request_id or "").strip()).with_for_update().one_or_none()
    if request is None:
        raise SpaceAccessError("access_request_not_found", "Access request not found.", status_code=404)
    location = str(request.location)
    operation = "space_access_admitted" if decision == "admitted" else "space_access_denied"
    key = _idempotency_key(idempotency_key)
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=key,
        operation=operation,
        location=location,
    )
    if existing is not None:
        return _receipt_payload(existing, replayed=True)
    policy = _policy(db, location, lock=True)
    if policy.controller_actor_id != context.actor_id:
        raise SpaceAccessError("not_space_controller", "Only this place's controller can resolve its requests.", status_code=403)
    if request.status != "pending":
        raise SpaceAccessError("request_already_resolved", "That access request was already resolved.")
    if decision not in ("admitted", "denied"):
        raise SpaceAccessError("invalid_decision", "Decision must be admitted or denied.", status_code=422)
    request.status = decision
    request.resolved_by_actor_id = context.actor_id
    request.resolved_at = _utcnow()
    if decision == "admitted":
        grant = (
            db.query(SpaceAccessGrant)
            .filter(
                SpaceAccessGrant.location == location,
                SpaceAccessGrant.actor_id == request.requester_actor_id,
            )
            .with_for_update()
            .one_or_none()
        )
        if grant is None:
            db.add(
                SpaceAccessGrant(
                    location=location,
                    actor_id=request.requester_actor_id,
                    active=True,
                    granted_by_actor_id=context.actor_id,
                )
            )
        else:
            grant.active = True
            grant.granted_by_actor_id = context.actor_id
            grant.revision = int(grant.revision or 1) + 1
    db.flush()
    result = {
        "request": {
            "request_id": str(request.request_id),
            "location": location,
            "requester_actor_id": str(request.requester_actor_id),
            "status": decision,
        }
    }
    try:
        return _record_receipt(
            db,
            context=context,
            idempotency_key=key,
            operation=operation,
            location=location,
            result=result,
        )
    except IntegrityError:
        return _recover_duplicate(db, context=context, idempotency_key=key, operation=operation, location=location)
