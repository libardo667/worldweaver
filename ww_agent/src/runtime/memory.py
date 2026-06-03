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

from src.runtime.drive import Embedder, _cosine
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


class MemoryRecall:
    """Relevance recall over kept memories — the same operation the drive vector
    runs over the soul, on a different store. Embed the moment, find the memories
    most aligned with it: not "the most recent things" but "what you recall *here*."

    Memory embeddings are cached by note text, so each note is embedded once; only
    the moment is embedded per call. With no embedder this is simply unused and
    callers fall back to recency.
    """

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._cache: dict[str, list[float]] = {}

    async def recall(self, notes: list[str], moment: str, *, top_k: int = 6) -> list[dict[str, Any]]:
        moment = str(moment or "").strip()
        notes = [n for n in (str(x).strip() for x in notes) if n]
        if not moment or not notes:
            return []
        fresh = [n for n in notes if n not in self._cache]
        if fresh:
            for note, vec in zip(fresh, await self._embedder.embed(fresh)):
                if vec:
                    self._cache[note] = vec
        query = (await self._embedder.embed([moment]) or [[]])[0]
        if not query:
            return []
        scored = [(n, _cosine(query, self._cache.get(n) or [])) for n in notes]
        scored = [(n, s) for n, s in scored if s > 0.0]
        scored.sort(key=lambda item: -item[1])
        return [{"note": n, "score": round(s, 4)} for n, s in scored[:top_k]]
