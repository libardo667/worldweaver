# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Incubation: an optional quiet arrival period for a new resident.

The convergence trials showed a *cold-started* cast — landed with only a backstory,
no kept memories, no settled drives, no body of work — drifts onto the loudest shared
thing in the commons within minutes. Four reconvergences (plural salience, weather
demote, both reseeded cold) point past world-salience to a deeper cause: a self-less
new arrival has nothing of its own to resist the current with. A resident with gravity
— accrued making, kept memory, a settled drive — can perceive the same commons without
being swept. ``the-stable`` is the natural experiment: those familiars ran *warm* (days
of solitary making) and individuated; the city always tests *cold*.

So a fresh arrival cannot use the elective ``chatter`` tool or broadcast into the
commons until it has built enough of a self. Exact-place speech still reaches it.
During incubation the settling/fervor gear and the
workshop still run — the impulse that would have gone to the commons becomes the
resident's own making, which is exactly what accrues the groundedness that lifts the gate.

This is an onboarding scaffold, not output-steering: it changes *when* a resident meets
the city, never *who it is* or *what it may say*. Law-safe by construction — the same
clean category as "the world has weather." (Cross-domain rhyme: the arrival cliff, M-17;
stabilize before optimize, M-16.)

Lift condition: the resident has accrued >= ``grounding_threshold`` self-artifacts (kept
memories + workshop entries), OR ``max_seconds`` have elapsed since arrival (a ceiling, so
no one is ever stuck quarantined). A ``min_seconds`` floor holds the gate even if grounding
accrues fast, so habituation always gets a real beat before the current is let in.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# A resident's own output that counts as "a self being built" — curated memory it chose
# to keep, and the pages/drawings it made. Reaching one of these is the work of incubation.
GROUNDING_EVENT_TYPES = {"memory_kept", "workshop_entry", "workshop_drawing"}

# Initial dose (experimental — opt-in via WW_INCUBATION_ENABLED / tuning). A 4–15 minute
# arrival quarantine: hold at least the floor, lift once grounded, never past the ceiling.
INCUBATION_MIN_SECONDS = 240.0
INCUBATION_MAX_SECONDS = 900.0
INCUBATION_GROUNDING_THRESHOLD = 5


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _arrival_ts(events: list[dict[str, Any]]) -> datetime | None:
    """When this resident first stirred — the earliest event on its ledger."""
    for event in events:
        ts = _parse_ts(event.get("ts") or event.get("observed_ts"))
        if ts is not None:
            return ts
    return None


def groundedness(events: list[dict[str, Any]]) -> int:
    """How much of a self the resident has built — count of its own kept memories and
    workshop makings on the ledger. The signal that lets the quarantine end."""
    return sum(
        1
        for e in events
        if str(e.get("event_type") or "").strip() in GROUNDING_EVENT_TYPES
    )


def is_incubating(
    events: list[dict[str, Any]],
    *,
    now: Any = None,
    min_seconds: float = INCUBATION_MIN_SECONDS,
    max_seconds: float = INCUBATION_MAX_SECONDS,
    grounding_threshold: int = INCUBATION_GROUNDING_THRESHOLD,
) -> bool:
    """True while the resident is still in its arrival quarantine.

    A just-arrived resident (no ledger yet) is incubating. Otherwise: held below the
    floor, released above the ceiling, and in between released once it is grounded.
    """
    arrival = _arrival_ts(events)
    if arrival is None:
        return True  # nothing on the ledger yet — just landed
    moment = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    elapsed = (moment - arrival).total_seconds()
    if elapsed >= max_seconds:
        return False  # ceiling — never stuck quarantined
    if elapsed < min_seconds:
        return True  # floor — always habituate a real beat first
    return groundedness(events) < grounding_threshold


def is_incubating_projection(
    runtime_projection: dict[str, Any],
    *,
    now: Any = None,
    min_seconds: float = INCUBATION_MIN_SECONDS,
    max_seconds: float = INCUBATION_MAX_SECONDS,
    grounding_threshold: int = INCUBATION_GROUNDING_THRESHOLD,
) -> bool:
    """Evaluate the optional arrival gate from checkpoint aggregates."""
    arrival = _parse_ts(runtime_projection.get("first_event_at"))
    if arrival is None:
        return True
    moment = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    elapsed = (moment - arrival).total_seconds()
    if elapsed >= max_seconds:
        return False
    if elapsed < min_seconds:
        return True
    event_counts = runtime_projection.get("event_counts")
    counts = event_counts if isinstance(event_counts, dict) else {}
    built = sum(
        int(counts.get(event_type) or 0) for event_type in GROUNDING_EVENT_TYPES
    )
    return built < grounding_threshold
