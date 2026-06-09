#!/usr/bin/env python3
"""Recompute the STRUCTURAL relationship claims from the durable kept_memory snapshot.

Cold-reproducible: reads only ../evidence/kept_memory/*.jsonl + ../evidence/roster.tsv (the
never-trimmed durable store), so any reviewer gets the same numbers off GitHub.

Reports, with the metric-confound correction stated up front:
  * first-name collisions (the monitor's bare-first-name match mis-attributes + self-links namesakes)
  * link count under the monitor's first-name metric vs clean FULL-NAME disambiguation
  * residents keeping about >= N distinct peers (first-name vs full-name)
  * directed edges, RECIPROCATED dyads
  * locality: within-cluster vs cross-cluster edge fraction (vs chance)

Usage: python3 relationship_graph.py [--snapshot ../evidence] [--floor 3]
"""
from __future__ import annotations
import argparse, json, re
from collections import Counter, defaultdict
from pathlib import Path


def load_roster(snap: Path) -> dict:
    R = {}
    for line in (snap / "roster.tsv").read_text().splitlines()[1:]:
        slug, name, home = (line.split("\t") + ["", ""])[:3]
        p = name.split()
        R[slug] = dict(full=name, first=p[0], last=p[-1], home=home)
    return R


def notes(snap: Path, slug: str) -> list[str]:
    f = snap / "kept_memory" / f"{slug}.jsonl"
    return [json.loads(l).get("note") or "" for l in f.open() if l.strip()] if f.exists() else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=Path(__file__).resolve().parent.parent / "evidence")
    ap.add_argument("--floor", type=int, default=3, help="distinct peers kept-about = 'a relational self'")
    a = ap.parse_args()
    R = load_roster(a.snapshot)
    allnotes = {s: notes(a.snapshot, s) for s in R}

    firsts = [d["first"] for d in R.values()]
    col = [(n, c) for n, c in Counter(firsts).items() if c > 1]
    print(f"residents: {len(R)} | first-name COLLISIONS (metric confound): {col or 'none'}")

    firstlink, fulllink = defaultdict(set), defaultdict(set)
    for s in R:
        blob = " ".join(allnotes[s])
        for s2, d2 in R.items():
            if s2 == s:
                continue
            if re.search(r"\b" + re.escape(d2["first"]) + r"\b", blob):
                firstlink[s].add(d2["first"])
            if re.search(r"\b" + re.escape(d2["full"]) + r"\b", blob):
                fulllink[s].add(s2)

    ge_first = sum(1 for s in R if len(firstlink[s]) >= a.floor)
    ge_full = sum(1 for s in R if len(fulllink[s]) >= a.floor)
    print(f"residents keeping about >= {a.floor} peers:  first-name metric = {ge_first}/{len(R)}  |  clean full-name = {ge_full}/{len(R)}")

    edges = {(s, s2) for s in R for s2 in fulllink[s]}
    recip = {frozenset((a_, b_)) for (a_, b_) in edges if (b_, a_) in edges}
    within = sum(1 for (a_, b_) in edges if R[a_]["home"] == R[b_]["home"])
    cross = len(edges) - within
    chance = (a.floor) / (len(R) - 1)  # rough: peers-in-own-cluster / others
    print(f"directed edges (A keeps about B): {len(edges)} | RECIPROCATED dyads (A<->B): {len(recip)} ({2*len(recip)}/{len(edges)} edges mutual)")
    print(f"locality: within-cluster {within} | cross {cross} | within-fraction {within/len(edges):.0%} (chance ~{chance:.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
