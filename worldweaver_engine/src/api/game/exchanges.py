# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Shared resident/player HTTP verbs for accepted object exchanges."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...services.actor_authority import (
    RequestActorCredentials,
    authorize_bound_session_actor_http,
    get_request_actor_credentials,
)
from ...services.consequence_objects import ConsequenceDomainError
from ...services.clock import Clock, get_world_clock
from ...services.object_exchange import (
    accept_object_exchange,
    cancel_object_exchange,
    decline_object_exchange,
    offer_object_exchange,
    visible_object_exchanges,
)

router = APIRouter(prefix="/world/exchanges", tags=["world exchanges"])


class ExchangeCommandRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    idempotency_key: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
    )


class ExchangeOfferRequest(ExchangeCommandRequest):
    recipient_session_id: str = Field(
        min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )
    offered_object_id: str = Field(min_length=1, max_length=36)
    requested_object_id: str = Field(min_length=1, max_length=36)


def _raise_http(exc: ConsequenceDomainError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


@router.get("")
def get_object_exchanges(
    session_id: str = Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
) -> dict[str, Any]:
    """Electively list only exchanges involving the caller."""

    authorize_bound_session_actor_http(
        db, credentials=credentials, session_id=session_id
    )
    try:
        return visible_object_exchanges(db, session_id=session_id)
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("")
def post_object_exchange_offer(
    payload: ExchangeOfferRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
    world_clock: Clock = Depends(get_world_clock),
) -> dict[str, Any]:
    """Offer one currently held object for one held by a present person."""

    authorize_bound_session_actor_http(
        db, credentials=credentials, session_id=payload.session_id
    )
    try:
        return offer_object_exchange(
            db,
            session_id=payload.session_id,
            recipient_session_id=payload.recipient_session_id,
            offered_object_id=payload.offered_object_id,
            requested_object_id=payload.requested_object_id,
            idempotency_key=payload.idempotency_key,
            now=world_clock.now(),
        )
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/{exchange_id}/accept")
def post_object_exchange_acceptance(
    exchange_id: str,
    payload: ExchangeCommandRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
    world_clock: Clock = Depends(get_world_clock),
) -> dict[str, Any]:
    """Accept exact terms and atomically swap both objects if still possible."""

    authorize_bound_session_actor_http(
        db, credentials=credentials, session_id=payload.session_id
    )
    try:
        return accept_object_exchange(
            db,
            session_id=payload.session_id,
            exchange_id=exchange_id,
            idempotency_key=payload.idempotency_key,
            now=world_clock.now(),
        )
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/{exchange_id}/decline")
def post_object_exchange_decline(
    exchange_id: str,
    payload: ExchangeCommandRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
    world_clock: Clock = Depends(get_world_clock),
) -> dict[str, Any]:
    """Decline exact terms without moving either object."""

    authorize_bound_session_actor_http(
        db, credentials=credentials, session_id=payload.session_id
    )
    try:
        return decline_object_exchange(
            db,
            session_id=payload.session_id,
            exchange_id=exchange_id,
            idempotency_key=payload.idempotency_key,
            now=world_clock.now(),
        )
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/{exchange_id}/cancel")
def post_object_exchange_cancellation(
    exchange_id: str,
    payload: ExchangeCommandRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
    world_clock: Clock = Depends(get_world_clock),
) -> dict[str, Any]:
    """Cancel an open proposal without moving either object."""

    authorize_bound_session_actor_http(
        db, credentials=credentials, session_id=payload.session_id
    )
    try:
        return cancel_object_exchange(
            db,
            session_id=payload.session_id,
            exchange_id=exchange_id,
            idempotency_key=payload.idempotency_key,
            now=world_clock.now(),
        )
    except ConsequenceDomainError as exc:
        _raise_http(exc)
