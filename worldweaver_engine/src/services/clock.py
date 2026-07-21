# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Small explicit clock boundary for production rules and accelerated tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    """The time source a rule may consult."""

    def now(self) -> datetime: ...


def utc_datetime(value: datetime) -> datetime:
    """Return one aware UTC datetime or reject an ambiguous value."""

    if value.tzinfo is None:
        raise ValueError("clock values must include a timezone")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class SystemClock:
    """The live shard clock."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class ControlledClock:
    """A monotonic wall clock advanced explicitly by a gym or test."""

    def __init__(self, started_at: datetime):
        self._now = utc_datetime(started_at)

    def now(self) -> datetime:
        return self._now

    def advance_to(self, target: datetime) -> datetime:
        normalized = utc_datetime(target)
        if normalized < self._now:
            raise ValueError("a controlled clock cannot move backward")
        self._now = normalized
        return self._now

    def advance(self, elapsed: timedelta) -> datetime:
        if elapsed.total_seconds() < 0:
            raise ValueError("a controlled clock cannot move backward")
        return self.advance_to(self._now + elapsed)
