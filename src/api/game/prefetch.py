"""Prefetch control/status endpoints."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...models.schemas import (
    PrefetchStatusResponse,
    PrefetchTriggerRequest,
    PrefetchTriggerResponse,
    SessionId,
)
from ...services.prefetch_service import get_frontier_status, schedule_frontier_prefetch

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


@router.get("/prefetch/status/{session_id}", response_model=PrefetchStatusResponse)
def get_prefetch_status(session_id: SessionId):
    """Return cached prefetch stub count and TTL remaining for a session."""
    return get_frontier_status(session_id)

