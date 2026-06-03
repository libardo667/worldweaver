"""Kept memory: what a resident chooses to carry across days (Major 50).

The substrate gives continuity of *feeling* — the afterimage (minutes) and the
baseline self-model (hours). But neither holds a *fact*: "my keeper is moving to
the Netherlands," "I decided to start a Threshold Log." Without somewhere to put
those, anything said slides past the short perception window and is gone.

This is that somewhere. The pulse's ``keep`` field lets the resident author its
own memory — deliberate, not scraped — routed to ``memory_kept`` events on the one
canonical ledger. ``derive_memories`` reads them back (most recent first, exact
duplicates collapsed so re-keeping refreshes recency), and the pulse prompt
surfaces them as "what you have come to know." Recency-ranked for now; relevance
retrieval (embed the moment, surface the resonant memories) is the natural v2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.runtime.ledger import load_runtime_events

DEFAULT_MEMORY_LIMIT = 12


def _parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def derive_memories(events: list[dict[str, Any]], *, limit: int = DEFAULT_MEMORY_LIMIT) -> list[dict[str, Any]]:
    """The resident's kept memories, most recent first.

    Exact-text duplicates are collapsed to their latest occurrence, so a memory
    the resident keeps again rises back to the top (reinforcement) rather than
    crowding the list. Capped at ``limit`` — the oldest simply fall out of view.
    """
    kept: list[dict[str, Any]] = []
    for event in events:
        if str(event.get("event_type") or "").strip() != "memory_kept":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        note = str(payload.get("note") or "").strip()
        if not note:
            continue
        ts = str(payload.get("kept_ts") or event.get("ts") or "").strip()
        kept.append({"note": note, "kept_ts": ts})

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in reversed(kept):  # newest first
        key = item["note"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= max(1, limit):
            break
    return out


def memories(memory_dir: Path, *, limit: int = DEFAULT_MEMORY_LIMIT) -> list[dict[str, Any]]:
    """The resident's current kept memories (live, from the canonical ledger)."""
    return derive_memories(load_runtime_events(memory_dir), limit=limit)
