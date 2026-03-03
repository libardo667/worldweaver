"""Debug runtime metrics endpoints."""

from fastapi import APIRouter, HTTPException

from ...config import settings
from ...services.runtime_metrics import get_metrics_snapshot

router = APIRouter()


@router.get("/debug/metrics")
def api_debug_metrics():
    """Return local-process runtime metrics for tuning and diagnostics."""
    if not settings.enable_dev_reset:
        raise HTTPException(status_code=404, detail="Not found")
    return get_metrics_snapshot()
