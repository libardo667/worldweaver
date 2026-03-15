"""Shared datetime utilities for state domain modules."""

from datetime import datetime, timezone
from typing import Any, Optional


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse an ISO datetime string (or None) back to a datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None
