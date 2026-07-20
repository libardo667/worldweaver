# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Shared human/resident HTTP verbs for canonical durable objects."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...services.consequence_objects import (
    ConsequenceDomainError,
    give_durable_object,
    inspect_durable_object,
    pick_up_durable_object,
    place_durable_object,
    visible_durable_objects,
)

router = APIRouter(prefix="/world/objects", tags=["world objects"])


class ObjectCommandRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    idempotency_key: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
    )


class GiveObjectRequest(ObjectCommandRequest):
    recipient_session_id: str = Field(
        min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )


def _raise_http(exc: ConsequenceDomainError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


@router.get("")
def list_world_objects(
    session_id: str = Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List only objects the caller carries or can see at their exact place."""

    try:
        objects = visible_durable_objects(db, session_id=session_id)
    except ConsequenceDomainError as exc:
        _raise_http(exc)
    return {"objects": objects, "count": len(objects)}


@router.get("/{object_id}")
def get_world_object(
    object_id: str,
    session_id: str = Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Inspect one carried or co-located object without a global object feed."""

    try:
        return {
            "object": inspect_durable_object(
                db, session_id=session_id, object_id=object_id
            )
        }
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/{object_id}/place")
def place_world_object(
    object_id: str,
    payload: ObjectCommandRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Place a carried object at the caller's exact current location."""

    try:
        return place_durable_object(
            db,
            session_id=payload.session_id,
            object_id=object_id,
            idempotency_key=payload.idempotency_key,
        ).to_dict()
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/{object_id}/pick-up")
def pick_up_world_object(
    object_id: str,
    payload: ObjectCommandRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reclaim an object the same stable actor ordinarily placed here."""

    try:
        return pick_up_durable_object(
            db,
            session_id=payload.session_id,
            object_id=object_id,
            idempotency_key=payload.idempotency_key,
        ).to_dict()
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/{object_id}/give")
def give_world_object(
    object_id: str,
    payload: GiveObjectRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Give a carried object to a stable actor at the same exact location."""

    try:
        return give_durable_object(
            db,
            session_id=payload.session_id,
            recipient_session_id=payload.recipient_session_id,
            object_id=object_id,
            idempotency_key=payload.idempotency_key,
        ).to_dict()
    except ConsequenceDomainError as exc:
        _raise_http(exc)
