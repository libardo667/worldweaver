# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Explicit resident-side clock for world and cognitive time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


class WorldClock(Protocol):
    """The time source used for resident experience and world-side effects."""

    def now(self) -> datetime: ...


def aware_utc(value: datetime) -> datetime:
    """Normalize one aware instant to UTC."""

    if value.tzinfo is None:
        raise ValueError("resident world clock values must include a timezone")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class SystemWorldClock:
    """Production resident clock backed by real UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class FixedWorldClock:
    """One controlled instant supplied by a bounded gym activation."""

    instant: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "instant", aware_utc(self.instant))

    def now(self) -> datetime:
        return self.instant
