# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Exact, two-party accepted exchanges of canonical durable objects."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import DurableObject, ExchangeReceipt, ObjectExchange, SessionVars
from .consequence_objects import (
    ActorContext,
    ConsequenceDomainError,
    consequence_actor_context,
    consequence_idempotency_key,
    durable_object_payload,
    require_consequence_capabilities,
)
from .event_submission import WorldEventCommand, structural_event_idempotency_key, submit_world_event
from .shard_experience import GameCapability


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _require_exchange_capabilities() -> None:
    require_consequence_capabilities(
        GameCapability.DURABLE_OBJECTS,
        GameCapability.CUSTODY,
        GameCapability.ATOMIC_GIVING,
        GameCapability.WITNESSED_EXCHANGE,
    )


def _session_location(row: SessionVars) -> str:
    raw = row.vars if isinstance(row.vars, dict) else {}
    nested = raw.get("variables")
    variables = nested if raw.get("_v") == 2 and isinstance(nested, dict) else raw
    return str(variables.get("location") or "").strip()


def _actor_present_at(db: Session, *, actor_id: str, location: str) -> bool:
    rows = db.query(SessionVars).filter(SessionVars.actor_id == actor_id).all()
    return any(_session_location(row) == location for row in rows)


def _locked_objects(db: Session, *object_ids: str) -> dict[str, DurableObject]:
    normalized = sorted({str(object_id or "").strip() for object_id in object_ids if str(object_id or "").strip()})
    rows = (
        db.query(DurableObject)
        .filter(
            DurableObject.object_id.in_(normalized),
            DurableObject.status == "active",
        )
        .order_by(DurableObject.object_id.asc())
        .with_for_update()
        .all()
    )
    by_id = {str(row.object_id): row for row in rows}
    if len(by_id) != len(normalized):
        raise ConsequenceDomainError("exchange_object_not_found", "One of the exchange objects no longer exists.", status_code=404)
    return by_id


def _exchange_row(db: Session, exchange_id: str, *, lock: bool = False) -> ObjectExchange:
    normalized = str(exchange_id or "").strip()
    query = db.query(ObjectExchange).filter(ObjectExchange.exchange_id == normalized)
    if lock:
        query = query.with_for_update()
    row = query.one_or_none()
    if row is None:
        raise ConsequenceDomainError("exchange_not_found", "Object exchange not found.", status_code=404)
    return row


def _object_rows_for_exchange(db: Session, row: ObjectExchange, *, lock: bool = False) -> tuple[DurableObject, DurableObject]:
    if lock:
        objects = _locked_objects(db, str(row.offered_object_id), str(row.requested_object_id))
    else:
        rows = db.query(DurableObject).filter(DurableObject.object_id.in_((row.offered_object_id, row.requested_object_id))).all()
        objects = {str(item.object_id): item for item in rows}
    offered = objects.get(str(row.offered_object_id))
    requested = objects.get(str(row.requested_object_id))
    if offered is None or requested is None:
        raise ConsequenceDomainError("exchange_object_not_found", "One of the exchange objects no longer exists.", status_code=404)
    return offered, requested


def _exchange_payload(
    row: ObjectExchange,
    *,
    offered: DurableObject,
    requested: DurableObject,
    viewer: ActorContext | None = None,
    counterpart_present: bool | None = None,
) -> dict[str, Any]:
    custody_ready = offered.custodian_actor_id == row.proposer_actor_id and requested.custodian_actor_id == row.recipient_actor_id and offered.status == "active" and requested.status == "active"
    payload: dict[str, Any] = {
        "exchange_id": str(row.exchange_id),
        "status": str(row.status),
        "proposer_actor_id": str(row.proposer_actor_id),
        "recipient_actor_id": str(row.recipient_actor_id),
        "offered_object": durable_object_payload(offered),
        "requested_object": durable_object_payload(requested),
        "offered_object_revision_at_offer": int(row.offered_object_revision),
        "requested_object_revision_at_offer": int(row.requested_object_revision),
        "offered_at_location": str(row.offered_at_location),
        "completed_at_location": str(row.completed_at_location or ""),
        "custody_ready": custody_ready,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }
    if viewer is not None:
        is_proposer = viewer.actor_id == row.proposer_actor_id
        is_recipient = viewer.actor_id == row.recipient_actor_id
        payload.update(
            {
                "viewer_role": "proposer" if is_proposer else "recipient" if is_recipient else "observer",
                "counterpart_present": bool(counterpart_present),
                "can_accept": bool(row.status == "open" and is_recipient and custody_ready and counterpart_present),
                "can_decline": bool(row.status == "open" and is_recipient),
                "can_cancel": bool(row.status == "open" and is_proposer),
            }
        )
    return payload


def _receipt_payload(row: ExchangeReceipt, *, replayed: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "replayed": replayed,
        "exchange": dict((row.payload_json or {}).get("exchange") or {}),
        "receipt": {
            "receipt_id": str(row.receipt_id),
            "operation": str(row.operation),
            "exchange_id": str(row.exchange_id),
            "world_event_id": int(row.world_event_id),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        },
    }


def _existing_receipt(
    db: Session,
    *,
    actor_id: str,
    idempotency_key: str,
    operation: str,
    exchange_id: str | None = None,
) -> ExchangeReceipt | None:
    row = (
        db.query(ExchangeReceipt)
        .filter(
            ExchangeReceipt.actor_id == actor_id,
            ExchangeReceipt.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if row is None:
        return None
    if row.operation != operation or (exchange_id is not None and row.exchange_id != exchange_id):
        raise ConsequenceDomainError("idempotency_conflict", "That retry key was already used for a different exchange command.")
    return row


def _finish_exchange_command(
    db: Session,
    *,
    context: ActorContext,
    key: str,
    operation: str,
    exchange: ObjectExchange,
    payload: dict[str, Any],
    summary: str,
    delta: dict[str, Any],
) -> dict[str, Any]:
    event = submit_world_event(
        db,
        WorldEventCommand(
            session_id=context.session_id,
            event_type=operation,
            summary=summary,
            delta=delta,
            metadata={"surface": "object_exchange_command", "actor_id": context.actor_id},
            idempotency_key=structural_event_idempotency_key(operation, key),
            skip_graph_extraction=True,
            skip_projection=True,
            preserve_event_type=True,
            defer_commit=True,
        ),
    )
    receipt = ExchangeReceipt(
        actor_id=context.actor_id,
        session_id=context.session_id,
        idempotency_key=key,
        operation=operation,
        exchange_id=str(exchange.exchange_id),
        world_event_id=event.event_id,
        payload_json={"exchange": payload},
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
    exchange_id: str | None = None,
) -> dict[str, Any]:
    db.rollback()
    row = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=key,
        operation=operation,
        exchange_id=exchange_id,
    )
    if row is None:
        raise ConsequenceDomainError("transaction_conflict", "The exchange command conflicted and was not applied.")
    return _receipt_payload(row, replayed=True)


def offer_object_exchange(
    db: Session,
    *,
    session_id: str,
    recipient_session_id: str,
    offered_object_id: str,
    requested_object_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    """Propose exact terms without reserving or moving either object."""

    _require_exchange_capabilities()
    context = consequence_actor_context(db, session_id)
    recipient = consequence_actor_context(db, recipient_session_id)
    key = consequence_idempotency_key(idempotency_key)
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=key,
        operation="object_exchange_offered",
    )
    if existing is not None:
        return _receipt_payload(existing, replayed=True)
    if context.actor_id == recipient.actor_id:
        raise ConsequenceDomainError("same_actor", "An actor cannot exchange objects with themself.", status_code=422)
    if context.location != recipient.location:
        raise ConsequenceDomainError("recipient_not_present", "Both people must be at the same exact location to offer an exchange.")
    if str(offered_object_id or "").strip() == str(requested_object_id or "").strip():
        raise ConsequenceDomainError("same_object", "An exchange must name two different objects.", status_code=422)

    try:
        objects = _locked_objects(db, offered_object_id, requested_object_id)
        offered = objects.get(str(offered_object_id or "").strip())
        requested = objects.get(str(requested_object_id or "").strip())
        if offered is None or requested is None:
            raise ConsequenceDomainError("exchange_object_not_found", "One of the exchange objects no longer exists.", status_code=404)
        if offered.custodian_actor_id != context.actor_id:
            raise ConsequenceDomainError("offered_object_not_held", "The proposer must currently hold the offered object.", status_code=403)
        if requested.custodian_actor_id != recipient.actor_id:
            raise ConsequenceDomainError("requested_object_not_held", "The recipient must currently hold the requested object.", status_code=403)
        exchange = ObjectExchange(
            proposer_actor_id=context.actor_id,
            recipient_actor_id=recipient.actor_id,
            offered_object_id=str(offered.object_id),
            requested_object_id=str(requested.object_id),
            offered_object_revision=int(offered.revision or 1),
            requested_object_revision=int(requested.revision or 1),
            status="open",
            offered_at_location=context.location,
        )
        db.add(exchange)
        db.flush()
        payload = _exchange_payload(exchange, offered=offered, requested=requested)
        return _finish_exchange_command(
            db,
            context=context,
            key=key,
            operation="object_exchange_offered",
            exchange=exchange,
            payload=payload,
            summary=f"{offered.name} is offered in exchange for {requested.name}.",
            delta={"object_exchange": payload},
        )
    except IntegrityError:
        return _recover_duplicate(
            db,
            context=context,
            key=key,
            operation="object_exchange_offered",
        )
    except Exception:
        db.rollback()
        raise


def accept_object_exchange(
    db: Session,
    *,
    session_id: str,
    exchange_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    """Recheck the exact terms and atomically swap both objects."""

    _require_exchange_capabilities()
    context = consequence_actor_context(db, session_id)
    key = consequence_idempotency_key(idempotency_key)
    normalized_id = str(exchange_id or "").strip()
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=key,
        operation="object_exchange_completed",
        exchange_id=normalized_id,
    )
    if existing is not None:
        return _receipt_payload(existing, replayed=True)

    try:
        exchange = _exchange_row(db, normalized_id, lock=True)
        existing = _existing_receipt(
            db,
            actor_id=context.actor_id,
            idempotency_key=key,
            operation="object_exchange_completed",
            exchange_id=normalized_id,
        )
        if existing is not None:
            return _receipt_payload(existing, replayed=True)
        if exchange.recipient_actor_id != context.actor_id:
            raise ConsequenceDomainError("not_exchange_recipient", "Only the named recipient can accept this exchange.", status_code=403)
        if exchange.status != "open":
            raise ConsequenceDomainError("exchange_not_open", "That exchange is no longer open.")
        if not _actor_present_at(db, actor_id=str(exchange.proposer_actor_id), location=context.location):
            raise ConsequenceDomainError("proposer_not_present", "Both people must be at the same exact location to complete an exchange.")
        offered, requested = _object_rows_for_exchange(db, exchange, lock=True)
        if offered.custodian_actor_id != exchange.proposer_actor_id:
            raise ConsequenceDomainError("exchange_terms_unavailable", "The proposer no longer holds the offered object.")
        if requested.custodian_actor_id != exchange.recipient_actor_id:
            raise ConsequenceDomainError("exchange_terms_unavailable", "The recipient no longer holds the requested object.")

        before = {
            "offered_object": durable_object_payload(offered),
            "requested_object": durable_object_payload(requested),
        }
        offered.custodian_actor_id = exchange.recipient_actor_id
        offered.placed_by_actor_id = None
        offered.revision = int(offered.revision or 1) + 1
        requested.custodian_actor_id = exchange.proposer_actor_id
        requested.placed_by_actor_id = None
        requested.revision = int(requested.revision or 1) + 1
        exchange.status = "completed"
        exchange.completed_at_location = context.location
        exchange.resolved_at = _utcnow()
        db.flush()
        payload = _exchange_payload(exchange, offered=offered, requested=requested)
        return _finish_exchange_command(
            db,
            context=context,
            key=key,
            operation="object_exchange_completed",
            exchange=exchange,
            payload=payload,
            summary=f"{offered.name} and {requested.name} change hands by agreement.",
            delta={
                "object_exchange": {
                    **payload,
                    "before": before,
                }
            },
        )
    except IntegrityError:
        return _recover_duplicate(
            db,
            context=context,
            key=key,
            operation="object_exchange_completed",
            exchange_id=normalized_id,
        )
    except Exception:
        db.rollback()
        raise


def _resolve_open_exchange(
    db: Session,
    *,
    session_id: str,
    exchange_id: str,
    idempotency_key: str,
    resolution: str,
) -> dict[str, Any]:
    _require_exchange_capabilities()
    context = consequence_actor_context(db, session_id)
    key = consequence_idempotency_key(idempotency_key)
    normalized_id = str(exchange_id or "").strip()
    operation = f"object_exchange_{resolution}"
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=key,
        operation=operation,
        exchange_id=normalized_id,
    )
    if existing is not None:
        return _receipt_payload(existing, replayed=True)
    try:
        exchange = _exchange_row(db, normalized_id, lock=True)
        if exchange.status != "open":
            raise ConsequenceDomainError("exchange_not_open", "That exchange is no longer open.")
        if resolution == "declined" and exchange.recipient_actor_id != context.actor_id:
            raise ConsequenceDomainError("not_exchange_recipient", "Only the named recipient can decline this exchange.", status_code=403)
        if resolution == "cancelled" and exchange.proposer_actor_id != context.actor_id:
            raise ConsequenceDomainError("not_exchange_proposer", "Only the proposer can cancel this exchange.", status_code=403)
        exchange.status = resolution
        exchange.resolved_at = _utcnow()
        offered, requested = _object_rows_for_exchange(db, exchange)
        db.flush()
        payload = _exchange_payload(exchange, offered=offered, requested=requested)
        verb = "declined" if resolution == "declined" else "cancelled"
        return _finish_exchange_command(
            db,
            context=context,
            key=key,
            operation=operation,
            exchange=exchange,
            payload=payload,
            summary=f"The exchange of {offered.name} for {requested.name} is {verb}.",
            delta={"object_exchange": payload},
        )
    except IntegrityError:
        return _recover_duplicate(
            db,
            context=context,
            key=key,
            operation=operation,
            exchange_id=normalized_id,
        )
    except Exception:
        db.rollback()
        raise


def decline_object_exchange(
    db: Session,
    *,
    session_id: str,
    exchange_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    return _resolve_open_exchange(
        db,
        session_id=session_id,
        exchange_id=exchange_id,
        idempotency_key=idempotency_key,
        resolution="declined",
    )


def cancel_object_exchange(
    db: Session,
    *,
    session_id: str,
    exchange_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    return _resolve_open_exchange(
        db,
        session_id=session_id,
        exchange_id=exchange_id,
        idempotency_key=idempotency_key,
        resolution="cancelled",
    )


def visible_object_exchanges(db: Session, *, session_id: str) -> dict[str, Any]:
    """Electively list the caller's exchanges and exact co-present offer options."""

    _require_exchange_capabilities()
    context = consequence_actor_context(db, session_id)
    rows = (
        db.query(ObjectExchange)
        .filter(
            or_(
                ObjectExchange.proposer_actor_id == context.actor_id,
                ObjectExchange.recipient_actor_id == context.actor_id,
            )
        )
        .order_by(ObjectExchange.created_at.desc(), ObjectExchange.exchange_id.desc())
        .limit(100)
        .all()
    )
    exchanges: list[dict[str, Any]] = []
    for row in rows:
        offered, requested = _object_rows_for_exchange(db, row)
        counterpart = row.recipient_actor_id if row.proposer_actor_id == context.actor_id else row.proposer_actor_id
        exchanges.append(
            _exchange_payload(
                row,
                offered=offered,
                requested=requested,
                viewer=context,
                counterpart_present=_actor_present_at(db, actor_id=str(counterpart), location=context.location),
            )
        )

    nearby_sessions: dict[str, SessionVars] = {}
    for row in db.query(SessionVars).order_by(SessionVars.session_id.asc()).all():
        actor_id = str(row.actor_id or "").strip()
        if not actor_id or actor_id == context.actor_id or _session_location(row) != context.location:
            continue
        nearby_sessions.setdefault(actor_id, row)
        if len(nearby_sessions) >= 12:
            break

    actor_ids = list(nearby_sessions)
    held_by_actor: dict[str, list[DurableObject]] = {actor_id: [] for actor_id in actor_ids}
    if actor_ids:
        held_rows = (
            db.query(DurableObject)
            .filter(
                DurableObject.custodian_actor_id.in_(actor_ids),
                DurableObject.status == "active",
            )
            .order_by(DurableObject.created_at.asc(), DurableObject.object_id.asc())
            .all()
        )
        for held in held_rows:
            actor_id = str(held.custodian_actor_id or "")
            if actor_id in held_by_actor and len(held_by_actor[actor_id]) < 12:
                held_by_actor[actor_id].append(held)

    offer_options = [
        {
            "recipient_actor_id": actor_id,
            "recipient_session_id": str(nearby_sessions[actor_id].session_id),
            "requested_objects": [durable_object_payload(item) for item in held_by_actor[actor_id]],
        }
        for actor_id in actor_ids
        if held_by_actor[actor_id]
    ]
    return {
        "exchanges": exchanges,
        "count": len(exchanges),
        "offer_options": offer_options,
    }
