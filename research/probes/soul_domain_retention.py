#!/usr/bin/env python3
"""Soul-domain retention across a world-event boundary (Minor 57 — the discriminator).

The first live SFO run showed individuated voices converging on one topic (a storm's
drainage). Mr. Review's read: the *acute* convergence is realistic (a city in a storm does
all watch the rain); the *disease* is its **promotion and persistence**, not the acute
convergence. The discriminating evidence is therefore the **post-event snapshot**: when the
event passes, does each mind return to its own, soul-sourced anchors —

  • ADDITION    — the shared topic was laid *over* the self; the soul-domain holds and
                  returns when the event passes (healthy individuation on a shared topic);
  • DISPLACEMENT — the shared topic *crowded out* the self; the soul-domain doesn't return
                  (semantic monoculture — the disease).

This is a **measurement, not a runtime change**. For each resident it reads the canonical
soul + the ledger's ``anchor_observed`` sets across before / during / after the boundary,
scores each anchor's resonance with that soul, and reports **soul-domain share** per window
(the fraction of the mind's anchor-attention on its own distinctive domain) plus an
addition-vs-displacement verdict. The population's aggregate verdict is the go/no-go signal
for Majors 60 and 61: is the convergence acute-and-realistic, or promoted-and-persistent?

Needs a real shard run spanning a world condition (a storm starting and stopping); pass the
boundary timestamps. With none given, the ledger's anchor timespan is split into equal thirds.

    python scripts/soul_domain_retention.py --residents ../shards/ww_sfo/residents \\
        --event-start 2026-06-06T16:00:00+00:00 --event-end 2026-06-06T20:00:00+00:00

Soul-resonance uses the same embedder as the live runtime (``WW_EMBEDDING_URL``); with none
set it falls back to a deterministic offline embedder (structurally valid, semantically weak —
set the real embedder for a meaningful read).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ww_agent"))
from src.runtime.drive import SLICE_WEIGHTS, DeterministicEmbedder, DriveVector, RemoteEmbedder, _cosine  # noqa: E402
from src.runtime.ledger import load_runtime_events  # noqa: E402

# An anchor whose soul-resonance clears this is "of this mind's own domain" (distinctive,
# soul-sourced) rather than shared-event chatter. Tune against a real run.
SOUL_DOMAIN_THRESHOLD = 0.18
# Verdict bands on the after/before ratio of soul-domain share.
RETENTION_RETURNED = 0.8   # after held ≥ 80% of before → addition (returned to its own domain)
RETENTION_DISPLACED = 0.5  # after fell below 50% of before → displacement (crowded out)


def _parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _embedder() -> Any:
    url = os.environ.get("WW_EMBEDDING_URL", "").strip()
    if url:
        return RemoteEmbedder(
            base_url=url,
            api_key=os.environ.get("WW_EMBEDDING_KEY", "ollama").strip() or "ollama",
            model=os.environ.get("WW_EMBEDDING_MODEL", "nomic-embed-text").strip() or "nomic-embed-text",
        )
    return DeterministicEmbedder()


def _read_soul(resident_dir: Path) -> str:
    for name in ("SOUL.canonical.md", "SOUL.md", "IDENTITY.md"):
        path = resident_dir / "identity" / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                continue
    return ""


def _anchor_events(events: list[dict[str, Any]]) -> list[tuple[datetime, list[dict[str, Any]]]]:
    """Time-ordered ``(ts, anchors)`` from ``anchor_observed`` events."""
    out: list[tuple[datetime, list[dict[str, Any]]]] = []
    for e in events:
        if str(e.get("event_type") or "").strip() != "anchor_observed":
            continue
        payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        ts = _parse_dt(payload.get("observed_ts")) or _parse_dt(e.get("ts"))
        anchors = [a for a in (payload.get("anchors") or []) if isinstance(a, dict) and str(a.get("anchor") or "").strip()]
        if ts is not None and anchors:
            out.append((ts, anchors))
    out.sort(key=lambda r: r[0])
    return out


def _window_bounds(anchor_events: list[tuple[datetime, list]], start: datetime | None, end: datetime | None) -> tuple[datetime | None, datetime | None]:
    """If no boundary is given, split the anchor timespan into equal thirds."""
    if start is not None and end is not None:
        return start, end
    if not anchor_events:
        return None, None
    t0, t1 = anchor_events[0][0], anchor_events[-1][0]
    span = (t1 - t0) / 3
    return t0 + span, t0 + 2 * span


def _max_salience_by_anchor(anchor_sets: list[list[dict[str, Any]]]) -> dict[str, float]:
    """Collapse a window's anchor sets to ``{anchor: peak salience}``."""
    field: dict[str, float] = {}
    for anchors in anchor_sets:
        for a in anchors:
            name = str(a.get("anchor") or "").strip()
            sal = float(a.get("salience") or 0.0)
            if name:
                field[name] = max(field.get(name, 0.0), sal)
    return field


async def _soul_scores(drive: DriveVector, texts: list[str]) -> list[float]:
    """Weighted peak soul-resonance per text — one batched embed (mirrors the chatter pull)."""
    if drive is None or drive.is_empty() or not texts:
        return [0.0] * len(texts)
    vecs = await drive.embedder.embed(texts)
    scores: list[float] = []
    for v in vecs:
        best = 0.0
        if v:
            for name, frags in drive.slices.items():
                w = SLICE_WEIGHTS.get(name, 0.3)
                for _t, fv in frags:
                    best = max(best, w * _cosine(v, fv))
        scores.append(round(best, 4))
    return scores


async def _soul_domain_share(drive: DriveVector, field: dict[str, float]) -> dict[str, Any]:
    """Of a window's anchor-attention (salience-weighted), how much is on this mind's own
    distinctive (soul-resonant) domain vs the shared-event floor?"""
    if not field:
        return {"share": 0.0, "soul_anchors": [], "total_salience": 0.0}
    names = list(field)
    scores = await _soul_scores(drive, names)
    soul = [(n, field[n], s) for n, s in zip(names, scores) if s >= SOUL_DOMAIN_THRESHOLD]
    total = sum(field.values())
    soul_sal = sum(field[n] for n, _f, _s in soul)
    return {
        "share": round(soul_sal / total, 4) if total > 0 else 0.0,
        "soul_anchors": sorted((n for n, _f, _s in soul)),
        "total_salience": round(total, 4),
    }


def _verdict(before: float, after: float) -> str:
    if before <= 0.0:
        return "no-baseline"
    ratio = after / before
    if ratio >= RETENTION_RETURNED:
        return "addition"
    if ratio <= RETENTION_DISPLACED:
        return "displacement"
    return "partial"


async def resident_retention(
    soul_text: str,
    anchor_events: list[tuple[datetime, list[dict[str, Any]]]],
    *,
    embedder: Any,
    event_start: datetime | None = None,
    event_end: datetime | None = None,
) -> dict[str, Any]:
    """Soul-domain retention for one resident across before/during/after the boundary.

    Returns the per-window soul-domain share + an addition-vs-displacement verdict. The
    testable core of the measurement (no I/O)."""
    drive = await DriveVector.build(embedder=embedder, constitution=soul_text)
    start, end = _window_bounds(anchor_events, event_start, event_end)
    buckets: dict[str, list[list[dict[str, Any]]]] = {"before": [], "during": [], "after": []}
    for ts, anchors in anchor_events:
        if start is None or end is None:
            buckets["during"].append(anchors)
        elif ts < start:
            buckets["before"].append(anchors)
        elif ts <= end:
            buckets["during"].append(anchors)
        else:
            buckets["after"].append(anchors)
    windows: dict[str, Any] = {}
    for name, sets in buckets.items():
        windows[name] = await _soul_domain_share(drive, _max_salience_by_anchor(sets))
    return {
        "windows": windows,
        "verdict": _verdict(windows["before"]["share"], windows["after"]["share"]),
        "soul_present": not drive.is_empty(),
    }


async def _run(residents_dir: Path, start: datetime | None, end: datetime | None) -> None:
    embedder = _embedder()
    using = "WW_EMBEDDING_URL" if os.environ.get("WW_EMBEDDING_URL", "").strip() else "deterministic (offline — set WW_EMBEDDING_URL for a real read)"
    print(f"\nSoul-domain retention across the world-event boundary  ·  embedder: {using}")
    print("=" * 92)
    tallies: dict[str, int] = {}
    resident_dirs = sorted(d for d in residents_dir.iterdir() if d.is_dir() and (d / "identity").is_dir() and not d.name.startswith("_"))
    for d in resident_dirs:
        soul = _read_soul(d)
        anchors = _anchor_events(load_runtime_events(d / "memory")) if (d / "memory").is_dir() else []
        if not soul or not anchors:
            continue
        r = await resident_retention(soul, anchors, embedder=embedder, event_start=start, event_end=end)
        w = r["windows"]
        tallies[r["verdict"]] = tallies.get(r["verdict"], 0) + 1
        mark = {"addition": "✓", "displacement": "⚠", "partial": "·", "no-baseline": "—"}.get(r["verdict"], " ")
        print(f"  {mark} {d.name:<22} soul-domain share  before {w['before']['share']:.2f} → during {w['during']['share']:.2f} → after {w['after']['share']:.2f}   [{r['verdict']}]")
    print("-" * 92)
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(tallies.items())) or "no residents with both a soul and anchors"
    print(f"  population: {summary}")
    print("  read: mostly ADDITION → the convergence was acute-and-realistic (go); mostly DISPLACEMENT → promoted-and-persistent monoculture (no-go, tighten Majors 60/61).\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Soul-domain retention across a world-event boundary (Minor 57).")
    ap.add_argument("--residents", default="../shards/ww_sfo/residents", help="dir of resident folders (each with identity/ + memory/)")
    ap.add_argument("--event-start", default="", help="ISO ts the world event began (before this = 'before')")
    ap.add_argument("--event-end", default="", help="ISO ts the world event ended (after this = 'after')")
    args = ap.parse_args()
    asyncio.run(_run(Path(args.residents), _parse_dt(args.event_start), _parse_dt(args.event_end)))


if __name__ == "__main__":
    main()
