# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Tombstones for the removed model-narrated freeform action surface."""

from fastapi import APIRouter, HTTPException

router = APIRouter()

_REMOVED_DETAIL = {
    "error": "freeform_action_removed",
    "message": (
        "Freeform narrated actions are no longer part of WorldWeaver. "
        "Use the concrete actions offered by the current place."
    ),
}


@router.post("/action")
def removed_freeform_action():
    """Keep old clients honest without interpreting or narrating their text."""
    raise HTTPException(status_code=410, detail=_REMOVED_DETAIL)


@router.post("/action/stream")
def removed_freeform_action_stream():
    """The former streaming narrator has the same explicit tombstone."""
    raise HTTPException(status_code=410, detail=_REMOVED_DETAIL)
