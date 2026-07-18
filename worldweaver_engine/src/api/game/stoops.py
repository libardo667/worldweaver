# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Shared resident/player HTTP verbs for single-instance world stoops."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...services.consequence_objects import ConsequenceDomainError
from ...services.world_stoops import (
    browse_world_stoop,
    leave_object_on_stoop,
    local_stoops,
    take_stoop_object,
    withdraw_stoop_object,
)

router = APIRouter(prefix="/world/stoops", tags=["world stoops"])


class StoopCommandRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class LeaveStoopObjectRequest(StoopCommandRequest):
    object_id: str = Field(min_length=1, max_length=36)


def _raise_http(exc: ConsequenceDomainError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


@router.get("")
def get_local_stoops(
    session_id: str = Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """See which bounded stoops are present here without opening them."""

    try:
        return local_stoops(db, session_id=session_id)
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.get("/{stoop_id}")
def get_world_stoop(
    stoop_id: str,
    session_id: str = Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Electively browse active entries while at this stoop's exact place."""

    try:
        return browse_world_stoop(db, session_id=session_id, stoop_id=stoop_id)
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/{stoop_id}/leave")
def post_leave_stoop_object(
    stoop_id: str,
    payload: LeaveStoopObjectRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Voluntarily leave one held object for any later visitor to take."""

    try:
        return leave_object_on_stoop(
            db,
            session_id=payload.session_id,
            stoop_id=stoop_id,
            object_id=payload.object_id,
            idempotency_key=payload.idempotency_key,
        )
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/entries/{entry_id}/take")
def post_take_stoop_object(
    entry_id: str,
    payload: StoopCommandRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Take one available object, atomically retiring its stoop entry."""

    try:
        return take_stoop_object(
            db,
            session_id=payload.session_id,
            entry_id=entry_id,
            idempotency_key=payload.idempotency_key,
        )
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/entries/{entry_id}/withdraw")
def post_withdraw_stoop_object(
    entry_id: str,
    payload: StoopCommandRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Let the original depositor reclaim an entry that remains available."""

    try:
        return withdraw_stoop_object(
            db,
            session_id=payload.session_id,
            entry_id=entry_id,
            idempotency_key=payload.idempotency_key,
        )
    except ConsequenceDomainError as exc:
        _raise_http(exc)
