# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Small in-process limits for public account-entry endpoints."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
import time

AUTH_RATE_LIMITED_PATHS = frozenset(
    {
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/request-password-reset",
        "/api/auth/reset-password",
    }
)


class FixedWindowRateLimiter:
    """Bound one key to a request count in the current minute."""

    def __init__(self) -> None:
        self._counts: dict[tuple[int, str], int] = defaultdict(int)
        self._window = -1
        self._lock = Lock()

    def allow(self, key: str, *, limit: int, now: float | None = None) -> tuple[bool, int]:
        if limit <= 0:
            return True, 0
        current = time.time() if now is None else now
        window = int(current // 60)
        with self._lock:
            if window != self._window:
                self._counts.clear()
                self._window = window
            bucket = (window, key)
            self._counts[bucket] += 1
            allowed = self._counts[bucket] <= limit
        retry_after = max(1, int(60 - current % 60))
        return allowed, retry_after
