# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Prefetch control/status endpoints."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...models.schemas import (
    PrefetchTriggerRequest,
    PrefetchTriggerResponse,
)
from ...services.prefetch_service import schedule_frontier_prefetch

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/prefetch/frontier", response_model=PrefetchTriggerResponse)
def trigger_prefetch_frontier(
    payload: PrefetchTriggerRequest,
    db: Session = Depends(get_db),
):
    """Schedule a best-effort background frontier prefetch and return immediately."""
    try:
        schedule_frontier_prefetch(
            payload.session_id,
            trigger="api_prefetch_frontier",
            bind=db.get_bind(),
        )
    except Exception as exc:
        logger.debug("Could not schedule prefetch via endpoint: %s", exc)
    return {"triggered": True}
