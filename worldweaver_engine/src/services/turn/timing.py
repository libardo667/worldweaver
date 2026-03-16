"""Shared timing helpers for turn orchestration."""

from __future__ import annotations

import time
from typing import Dict


def record_timing(
    timings_ms: Dict[str, float] | None,
    key: str,
    started: float,
) -> None:
    if timings_ms is None:
        return
    timings_ms[key] = round((time.perf_counter() - started) * 1000.0, 3)
