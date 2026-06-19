# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

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

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.runtime.drive import Embedder, _cosine
from src.runtime.ledger import load_runtime_events

DEFAULT_MEMORY_LIMIT = 12

# Kept memory must outlive the rolling event ledger. The ledger is hard-capped at
# the last N events (ledger._MAX_EVENTS), which at the substrate's event rate is
# only a few hours — so a ``memory_kept`` event left there is silently *evicted*,
# and the resident forgets what it deliberately chose to carry "across days". This
# is the durable store that fixes that: an append-only file, never trimmed, that is
# the real home of kept memory. The ledger event is kept too (for in-session
# provenance), but ``memories()`` reads from here and lazily rescues any ledger
# keepsakes into it before they can scroll off the back.
KEPT_STORE_NAME = "kept_memory.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _kept_path(memory_dir: Path) -> Path:
    return Path(memory_dir) / KEPT_STORE_NAME


def _load_kept_records(memory_dir: Path) -> list[dict[str, Any]]:
    """The durable kept-memory records (append order = chronological)."""
    path = _kept_path(memory_dir)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        note = str(data.get("note") or "").strip()
        if note:
            out.append({"note": note, "kept_ts": str(data.get("kept_ts") or "").strip()})
    return out


def record_kept(memory_dir: Path, note: str, *, kept_ts: str = "") -> None:
    """Append a kept memory to the durable store. Append-always — re-keeping the
    same note adds a line (reinforcement); ``derive_memories`` collapses exact
    duplicates to their latest occurrence, so the list stays clean."""
    note = str(note or "").strip()
    if not note:
        return
    path = _kept_path(memory_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"note": note, "kept_ts": str(kept_ts or _now_iso())}, ensure_ascii=False) + "\n")


def _ledger_kept_records(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    for event in events:
        if str(event.get("event_type") or "").strip() != "memory_kept":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        note = str(payload.get("note") or "").strip()
        if note:
            recs.append({"note": note, "kept_ts": str(payload.get("kept_ts") or event.get("ts") or "").strip()})
    return recs


def _records_to_events(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wrap kept records as synthetic ``memory_kept`` events so the one derive path
    (newest-first, exact-dup collapse) serves both the durable store and the ledger."""
    return [{"event_type": "memory_kept", "ts": r.get("kept_ts", ""), "payload": {"note": r["note"], "kept_ts": r.get("kept_ts", "")}} for r in records]


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
    """The resident's durable kept memories, most recent first — what it carries
    across days. Reads the durable store, and first *rescues* any keepsakes still
    sitting in the rolling ledger into it (migration of survivors + safety net), so
    a memory is preserved long before the ledger's hard cap could evict it."""
    memory_dir = Path(memory_dir)
    durable = _load_kept_records(memory_dir)
    seen = {r["note"].strip().lower() for r in durable}
    for r in _ledger_kept_records(load_runtime_events(memory_dir)):
        key = r["note"].strip().lower()
        if key not in seen:
            record_kept(memory_dir, r["note"], kept_ts=r["kept_ts"])
            durable.append(r)
            seen.add(key)
    return derive_memories(_records_to_events(durable), limit=limit)


class MemoryRecall:
    """Relevance recall over kept memories — the same operation the drive vector
    runs over the soul, on a different store. Embed the moment, find the memories
    most aligned with it: not "the most recent things" but "what you recall *here*."

    Memory embeddings are cached by note text, so each note is embedded once; only
    the moment is embedded per call. With no embedder this is simply unused and
    callers fall back to recency.
    """

    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder
        self._cache: dict[str, list[float]] = {}

    async def _ensure(self, notes: list[str]) -> None:
        fresh = [n for n in notes if n not in self._cache]
        if fresh:
            for note, vec in zip(fresh, await self.embedder.embed(fresh)):
                if vec:
                    self._cache[note] = vec

    async def recall(self, notes: list[str], moment: str, *, top_k: int = 6, diversity: float = 0.45) -> list[dict[str, Any]]:
        """The memories most relevant to the moment, picked for relevance AND
        mutual diversity (maximal marginal relevance). Without the diversity term a
        cluster of near-duplicate memories (e.g. a dozen lines all circling the
        same move) would crowd out everything else and re-prime the same groove;
        MMR surfaces one of them plus genuinely different recollections."""
        moment = str(moment or "").strip()
        notes = [n for n in (str(x).strip() for x in notes) if n]
        if not moment or not notes:
            return []
        await self._ensure(notes)
        query = (await self.embedder.embed([moment]) or [[]])[0]
        if not query:
            return []
        rel = {n: _cosine(query, self._cache.get(n) or []) for n in notes}
        candidates = [n for n in notes if rel[n] > 0.0]
        selected: list[str] = []
        while candidates and len(selected) < top_k:

            def mmr(n: str) -> float:
                redundancy = max((_cosine(self._cache[n], self._cache[s]) for s in selected if s in self._cache), default=0.0)
                return (1.0 - diversity) * rel[n] - diversity * redundancy

            best = max(candidates, key=mmr)
            selected.append(best)
            candidates.remove(best)
        return [{"note": n, "score": round(rel[n], 4)} for n in selected]

    async def novel(self, candidates: list[str], existing: list[str], *, threshold: float = 0.78) -> list[str]:
        """Of the candidate notes, those that are NOT a near-duplicate of an already
        held memory (nor of each other). Stops a resident from re-storing the same
        understanding in fresh words — which would otherwise pile up and re-prime a
        groove. The storage-time analogue of habituation: only genuinely new
        knowledge is kept."""
        cands = [c for c in (str(x).strip() for x in candidates) if c]
        olds = [e for e in (str(x).strip() for x in existing) if e]
        if not cands:
            return []
        await self._ensure(cands + olds)
        kept: list[str] = []
        for c in cands:
            cv = self._cache.get(c)
            if not cv:
                kept.append(c)
                continue
            if any(_cosine(cv, self._cache.get(o) or []) > threshold for o in olds):
                continue
            if any(_cosine(cv, self._cache.get(k) or []) > threshold for k in kept):
                continue
            kept.append(c)
        return kept
