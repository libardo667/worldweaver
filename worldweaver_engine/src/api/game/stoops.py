# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Shared resident/player HTTP verbs for single-instance world stoops."""

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
from ...services.world_stoops import (
    browse_world_stoop,
    browse_world_stoop_at,
    leave_object_on_stoop,
    local_stoops,
    local_stoops_at,
    take_stoop_object,
    withdraw_stoop_object,
)

router = APIRouter(prefix="/world/stoops", tags=["world stoops"])


class StoopCommandRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    idempotency_key: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
    )


class LeaveStoopObjectRequest(StoopCommandRequest):
    object_id: str = Field(min_length=1, max_length=36)


def _raise_http(exc: ConsequenceDomainError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


@router.get("")
def get_local_stoops(
    session_id: str | None = Query(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    ),
    location: str | None = Query(default=None, min_length=1, max_length=200),
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
) -> dict[str, Any]:
    """See which bounded stoops are present here without opening them.

    Embodied callers pass session_id (their own place is used); sessionless
    public onlookers pass the location they are viewing instead.
    """

    try:
        if session_id:
            authorize_bound_session_actor_http(
                db, credentials=credentials, session_id=session_id
            )
            return local_stoops(db, session_id=session_id)
        if location:
            return local_stoops_at(db, location=location)
        raise HTTPException(status_code=422, detail="Provide session_id or location.")
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.get("/{stoop_id}")
def get_world_stoop(
    stoop_id: str,
    session_id: str | None = Query(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    ),
    location: str | None = Query(default=None, min_length=1, max_length=200),
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
) -> dict[str, Any]:
    """Electively browse active entries while at this stoop's exact place.

    Sessionless public onlookers pass the location they are viewing; their
    entries carry no take/withdraw affordances.
    """

    try:
        if session_id:
            authorize_bound_session_actor_http(
                db, credentials=credentials, session_id=session_id
            )
            return browse_world_stoop(db, session_id=session_id, stoop_id=stoop_id)
        if location:
            return browse_world_stoop_at(db, location=location, stoop_id=stoop_id)
        raise HTTPException(status_code=422, detail="Provide session_id or location.")
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/{stoop_id}/leave")
def post_leave_stoop_object(
    stoop_id: str,
    payload: LeaveStoopObjectRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
    world_clock: Clock = Depends(get_world_clock),
) -> dict[str, Any]:
    """Voluntarily leave one held object for any later visitor to take."""

    authorize_bound_session_actor_http(
        db, credentials=credentials, session_id=payload.session_id
    )
    try:
        return leave_object_on_stoop(
            db,
            session_id=payload.session_id,
            stoop_id=stoop_id,
            object_id=payload.object_id,
            idempotency_key=payload.idempotency_key,
            now=world_clock.now(),
        )
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/entries/{entry_id}/take")
def post_take_stoop_object(
    entry_id: str,
    payload: StoopCommandRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
    world_clock: Clock = Depends(get_world_clock),
) -> dict[str, Any]:
    """Take one available object, atomically retiring its stoop entry."""

    authorize_bound_session_actor_http(
        db, credentials=credentials, session_id=payload.session_id
    )
    try:
        return take_stoop_object(
            db,
            session_id=payload.session_id,
            entry_id=entry_id,
            idempotency_key=payload.idempotency_key,
            now=world_clock.now(),
        )
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/entries/{entry_id}/withdraw")
def post_withdraw_stoop_object(
    entry_id: str,
    payload: StoopCommandRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
    world_clock: Clock = Depends(get_world_clock),
) -> dict[str, Any]:
    """Let the original depositor reclaim an entry that remains available."""

    authorize_bound_session_actor_http(
        db, credentials=credentials, session_id=payload.session_id
    )
    try:
        return withdraw_stoop_object(
            db,
            session_id=payload.session_id,
            entry_id=entry_id,
            idempotency_key=payload.idempotency_key,
            now=world_clock.now(),
        )
    except ConsequenceDomainError as exc:
        _raise_http(exc)
