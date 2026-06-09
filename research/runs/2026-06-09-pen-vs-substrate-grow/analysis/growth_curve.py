#!/usr/bin/env python3
"""Recompute the two growth curves (EXTENT vs DEPTH) from the durable kept_memory snapshot.

Cold-reproducible from ../evidence/kept_memory/*.jsonl + roster.tsv (each keep carries kept_ts).
The point: the acquaintance graph (EXTENT = distinct A->B links) saturates fast, while the
keep-weight (DEPTH = total keeps) keeps flowing ~linearly. This is why a stop-rule on extent alone
over-cuts, and what "matured" means precisely (edge SET frozen, edge WEIGHTS still climbing).

Usage: python3 growth_curve.py [--snapshot ../evidence] [--bucket-min 10]
"""
from __future__ import annotations
import argparse, json, re
from datetime import datetime
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=Path(__file__).resolve().parent.parent / "evidence")
    ap.add_argument("--bucket-min", type=int, default=10)
    a = ap.parse_args()

    R = {}
    for line in (a.snapshot / "roster.tsv").read_text().splitlines()[1:]:
        slug, name, *_ = line.split("\t")
        R[slug] = name

    events = []
    for s, full_self in R.items():
        f = a.snapshot / "kept_memory" / f"{s}.jsonl"
        if not f.exists():
            continue
        for l in f.open():
            if not l.strip():
                continue
            d = json.loads(l)
            note, ts = d.get("note", ""), d.get("kept_ts")
            if not ts:
                continue
            peers = {s2 for s2, full in R.items() if s2 != s and re.search(r"\b" + re.escape(full) + r"\b", note)}
            events.append((datetime.fromisoformat(ts), s, peers))
    events.sort()
    t0 = events[0][0]
    print(f"keeps={len(events)} | span {events[0][0].strftime('%H:%M')}->{events[-1][0].strftime('%H:%M')} ({(events[-1][0]-t0).total_seconds()/60:.0f} min)\n")

    seen, buckets = set(), {}
    for ts, s, peers in events:
        b = int((ts - t0).total_seconds() // (a.bucket_min * 60))
        nl, nk = buckets.get(b, (0, 0))
        nk += 1
        for p in peers:
            if (s, p) not in seen:
                seen.add((s, p)); nl += 1
        buckets[b] = (nl, nk)

    print(f"{'min':>5} {'NEW-links(EXTENT)':>17} {'NEW-keeps(DEPTH)':>16}")
    for b in range(max(buckets) + 1):
        nl, nk = buckets.get(b, (0, 0))
        print(f"{b*a.bucket_min:5} {nl:17} {nk:16}  {'#'*nl}")
    import statistics as st
    th = (max(buckets) + 1) // 3
    print(f"\nNEW-links/bucket  first third: {st.mean([buckets.get(b,(0,0))[0] for b in range(th+1)]):.1f}  last third: {st.mean([buckets.get(b,(0,0))[0] for b in range(2*th, max(buckets)+1)]):.1f}  <- EXTENT decays")
    print(f"NEW-keeps/bucket  first third: {st.mean([buckets.get(b,(0,0))[1] for b in range(th+1)]):.1f}  last third: {st.mean([buckets.get(b,(0,0))[1] for b in range(2*th, max(buckets)+1)]):.1f}  <- DEPTH holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
