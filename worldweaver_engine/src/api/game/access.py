# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Shared resident/player verbs for ordinary space access."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...services.space_access import (
    SpaceAccessError,
    access_status,
    invite_to_space,
    pending_requests,
    request_space_access,
    resolve_access_request,
    revoke_space_access,
    set_space_mode,
)

router = APIRouter(prefix="/world/access", tags=["world access"])


class AccessCommandRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    location: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class AccessRequestCommand(AccessCommandRequest):
    note: str = Field(default="", max_length=500)


class SpaceModeCommand(AccessCommandRequest):
    mode: Literal["public", "requestable", "private", "closed"]
    note: str | None = Field(default=None, max_length=500)


class AdmissionCommand(AccessCommandRequest):
    recipient_session_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class ResolveRequestCommand(BaseModel):
    session_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    decision: Literal["admitted", "denied"]
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


def _raise_http(exc: SpaceAccessError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


@router.get("")
def get_access_status(
    session_id: str = Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    location: str = Query(min_length=1, max_length=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Electively inspect the caller's access to one exact place."""

    try:
        return {"access": access_status(db, session_id=session_id, location=location)}
    except SpaceAccessError as exc:
        _raise_http(exc)


@router.get("/requests")
def get_pending_access_requests(
    session_id: str = Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    location: str = Query(min_length=1, max_length=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Electively review one controlled place's pending requests."""

    try:
        return pending_requests(db, session_id=session_id, location=location)
    except SpaceAccessError as exc:
        _raise_http(exc)


@router.post("/requests")
def post_access_request(
    payload: AccessRequestCommand,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ask to enter a requestable place without generating a scene prompt."""

    try:
        return request_space_access(
            db,
            session_id=payload.session_id,
            location=payload.location,
            idempotency_key=payload.idempotency_key,
            note=payload.note,
        )
    except SpaceAccessError as exc:
        _raise_http(exc)


@router.post("/requests/{request_id}/resolve")
def post_resolve_access_request(
    request_id: str,
    payload: ResolveRequestCommand,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Admit or decline one pending request as the place controller."""

    try:
        return resolve_access_request(
            db,
            session_id=payload.session_id,
            request_id=request_id,
            decision=payload.decision,
            idempotency_key=payload.idempotency_key,
        )
    except SpaceAccessError as exc:
        _raise_http(exc)


@router.post("/invite")
def post_space_invitation(
    payload: AdmissionCommand,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Explicitly admit one stable actor to a controlled place."""

    try:
        return invite_to_space(
            db,
            session_id=payload.session_id,
            recipient_session_id=payload.recipient_session_id,
            location=payload.location,
            idempotency_key=payload.idempotency_key,
        )
    except SpaceAccessError as exc:
        _raise_http(exc)


@router.post("/revoke")
def post_space_access_revocation(
    payload: AdmissionCommand,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """End one actor's future entry without ejecting or trapping anyone."""

    try:
        return revoke_space_access(
            db,
            session_id=payload.session_id,
            recipient_session_id=payload.recipient_session_id,
            location=payload.location,
            idempotency_key=payload.idempotency_key,
        )
    except SpaceAccessError as exc:
        _raise_http(exc)


@router.post("/mode")
def post_space_mode(
    payload: SpaceModeCommand,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Open, make requestable/private, or close one controlled place."""

    try:
        return set_space_mode(
            db,
            session_id=payload.session_id,
            location=payload.location,
            mode=payload.mode,
            idempotency_key=payload.idempotency_key,
            note=payload.note,
        )
    except SpaceAccessError as exc:
        _raise_http(exc)
