# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Elective local material browsing and structured making commands."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...services.consequence_objects import ConsequenceDomainError
from ...services.material_making import make_durable_object, making_catalog

router = APIRouter(prefix="/world", tags=["world making"])


class MakeObjectRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    recipe_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9._-]+$")
    idempotency_key: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
    )


def _raise_http(exc: ConsequenceDomainError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


@router.get("/making")
def get_local_making_catalog(
    session_id: str = Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Electively inspect only materials and recipes available right here."""

    try:
        return making_catalog(db, session_id=session_id)
    except ConsequenceDomainError as exc:
        _raise_http(exc)


@router.post("/make")
def post_make_object(
    payload: MakeObjectRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Make one declared object through the typed consequence boundary."""

    try:
        return make_durable_object(
            db,
            session_id=payload.session_id,
            recipe_id=payload.recipe_id,
            idempotency_key=payload.idempotency_key,
        ).to_dict()
    except ConsequenceDomainError as exc:
        _raise_http(exc)
