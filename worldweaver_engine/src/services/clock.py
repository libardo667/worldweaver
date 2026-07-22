# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Small explicit clock boundary for production rules and accelerated tests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Protocol

SCHEDULE_SCHEMA = "worldweaver.scheduled-event-queue"
SCHEDULE_SCHEMA_VERSION = 1
_EVENT_KIND_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class Clock(Protocol):
    """The time source a rule may consult."""

    def now(self) -> datetime: ...


def utc_datetime(value: datetime) -> datetime:
    """Return one aware UTC datetime or reject an ambiguous value."""

    if value.tzinfo is None:
        raise ValueError("clock values must include a timezone")
    return value.astimezone(timezone.utc)


def utc_naive(value: datetime) -> datetime:
    """Normalize one aware instant for the engine's UTC-naive SQL columns."""

    return utc_datetime(value).replace(tzinfo=None)


@dataclass(frozen=True, slots=True)
class SystemClock:
    """The live shard clock."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


def get_world_clock() -> Clock:
    """Return the request-scoped world clock used by live HTTP routes.

    FastAPI dependency overrides may replace this with a controlled clock for
    an isolated gym. Security expiry, request nonces, process timing, and model
    latency deliberately do not use this dependency.
    """

    return SystemClock()


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


@dataclass(frozen=True, slots=True)
class ScheduledEvent:
    """One serializable instruction waiting for its UTC deadline."""

    event_id: str
    sequence: int
    due_at: datetime
    kind: str
    payload: dict[str, Any]

    def as_payload(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "due_at": self.due_at.isoformat(),
            "kind": self.kind,
            "payload": json.loads(json.dumps(self.payload)),
        }


class ScheduledEventQueue:
    """Deterministic, checkpointable, at-least-once scheduled delivery.

    Due events remain in the queue until their handler explicitly acknowledges
    them. A crash before acknowledgement therefore causes a safe re-offer after
    restore; handlers that mutate state must use ``event_id`` as an idempotency
    key. The queue does not claim impossible exactly-once delivery.
    """

    def __init__(
        self,
        clock: ControlledClock,
        *,
        pending: Iterable[ScheduledEvent] = (),
        next_sequence: int = 1,
    ) -> None:
        self.clock = clock
        self._pending = list(pending)
        self._next_sequence = int(next_sequence)
        self._validate_state()

    def _validate_state(self) -> None:
        if self._next_sequence < 1:
            raise ValueError("scheduled event sequence must be positive")
        event_ids: set[str] = set()
        sequences: set[int] = set()
        for event in self._pending:
            if not event.event_id or event.event_id in event_ids:
                raise ValueError("scheduled event IDs must be unique")
            if event.sequence < 1 or event.sequence in sequences:
                raise ValueError(
                    "scheduled event sequences must be unique and positive"
                )
            if not _EVENT_KIND_RE.fullmatch(event.kind):
                raise ValueError("scheduled event kind is invalid")
            utc_datetime(event.due_at)
            json.dumps(event.payload)
            event_ids.add(event.event_id)
            sequences.add(event.sequence)
        if sequences and self._next_sequence <= max(sequences):
            raise ValueError("next scheduled event sequence must follow pending events")

    @staticmethod
    def _sort_key(event: ScheduledEvent) -> tuple[datetime, int]:
        return event.due_at, event.sequence

    @property
    def pending(self) -> tuple[ScheduledEvent, ...]:
        return tuple(sorted(self._pending, key=self._sort_key))

    def cancel(self, event_ids: Iterable[str]) -> tuple[str, ...]:
        """Remove exact pending events when their authoritative owner withdraws them."""

        requested = {str(event_id or "").strip() for event_id in event_ids}
        requested.discard("")
        removed = tuple(
            event.event_id for event in self.pending if event.event_id in requested
        )
        if removed:
            removed_set = set(removed)
            self._pending = [
                event for event in self._pending if event.event_id not in removed_set
            ]
        return removed

    def schedule_at(
        self,
        due_at: datetime,
        *,
        kind: str,
        payload: dict[str, Any] | None = None,
    ) -> ScheduledEvent:
        normalized_due_at = utc_datetime(due_at)
        if normalized_due_at < self.clock.now():
            raise ValueError("a scheduled event cannot be placed in the past")
        normalized_kind = str(kind or "").strip()
        if not _EVENT_KIND_RE.fullmatch(normalized_kind):
            raise ValueError("scheduled event kind is invalid")
        try:
            normalized_payload = json.loads(json.dumps(dict(payload or {})))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "scheduled event payload must be JSON serializable"
            ) from exc
        sequence = self._next_sequence
        self._next_sequence += 1
        event = ScheduledEvent(
            event_id=f"scheduled-{sequence:08d}",
            sequence=sequence,
            due_at=normalized_due_at,
            kind=normalized_kind,
            payload=normalized_payload,
        )
        self._pending.append(event)
        return event

    def advance_to_next(self) -> tuple[ScheduledEvent, ...]:
        """Move to the next deadline and offer every event due then."""

        if not self._pending:
            return ()
        next_due_at = min(event.due_at for event in self._pending)
        if next_due_at > self.clock.now():
            self.clock.advance_to(next_due_at)
        return self.due_events()

    def due_events(self) -> tuple[ScheduledEvent, ...]:
        """Offer due events without consuming them."""

        current = self.clock.now()
        return tuple(event for event in self.pending if event.due_at <= current)

    def acknowledge(self, event_ids: Iterable[str]) -> tuple[str, ...]:
        """Remove exact offered events after their handlers succeed."""

        normalized_ids = tuple(
            dict.fromkeys(str(event_id or "").strip() for event_id in event_ids)
        )
        normalized_ids = tuple(event_id for event_id in normalized_ids if event_id)
        if not normalized_ids:
            return ()
        due_ids = {event.event_id for event in self.due_events()}
        requested = set(normalized_ids)
        if not requested <= due_ids:
            raise ValueError("only currently due scheduled events may be acknowledged")
        self._pending = [
            event for event in self._pending if event.event_id not in requested
        ]
        return tuple(event_id for event_id in normalized_ids if event_id in requested)

    def as_payload(self) -> dict[str, Any]:
        """Return a JSON-safe checkpoint with every unacknowledged event."""

        return {
            "schema": SCHEDULE_SCHEMA,
            "schema_version": SCHEDULE_SCHEMA_VERSION,
            "clock_now": self.clock.now().isoformat(),
            "next_sequence": self._next_sequence,
            "pending": [event.as_payload() for event in self.pending],
        }

    @classmethod
    def from_payload(cls, raw: dict[str, Any]) -> "ScheduledEventQueue":
        if raw.get("schema") != SCHEDULE_SCHEMA:
            raise ValueError("unsupported scheduled event queue schema")
        if raw.get("schema_version") != SCHEDULE_SCHEMA_VERSION:
            raise ValueError("unsupported scheduled event queue version")
        try:
            clock_now = utc_datetime(datetime.fromisoformat(str(raw["clock_now"])))
            next_sequence = int(raw["next_sequence"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("scheduled event queue checkpoint is invalid") from exc
        pending_raw = raw.get("pending")
        if not isinstance(pending_raw, list):
            raise ValueError("scheduled event queue pending list is invalid")
        pending: list[ScheduledEvent] = []
        try:
            for item in pending_raw:
                if not isinstance(item, dict) or not isinstance(
                    item.get("payload"), dict
                ):
                    raise ValueError
                pending.append(
                    ScheduledEvent(
                        event_id=str(item["event_id"]),
                        sequence=int(item["sequence"]),
                        due_at=utc_datetime(
                            datetime.fromisoformat(str(item["due_at"]))
                        ),
                        kind=str(item["kind"]),
                        payload=json.loads(json.dumps(item["payload"])),
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("scheduled event queue checkpoint is invalid") from exc
        return cls(
            ControlledClock(clock_now),
            pending=pending,
            next_sequence=next_sequence,
        )
