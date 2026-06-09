#!/usr/bin/env python3
"""Recompute GROUNDING + SELECTIVITY from the ledger snapshot (~2h window, ~10:54-12:57).

The skeptical test: are kept impressions of peers grounded in actual perception, or pen-confabulated?
And among perceived peers, is keeping SELECTIVE (salience-driven) or indiscriminate? Reads only the
ledger snapshot ../evidence/ledgers/*.jsonl.gz, so it is cold-reproducible (a different, later window
than the live read first reported to the operator — this recompute is the artifact of record).

SUBSTRATE-ONLY grounding: a kept peer counts as grounded only via signals the substrate computes from
perception BEFORE the pen pulse fires — `anchor_observed` salience anchors and `packet_emitted` heard
packets — NOT the pen's own address-target (that would be circular: keep + address in one pulse).

Usage: python3 grounding_selectivity.py [--snapshot ../evidence]
"""
from __future__ import annotations
import argparse, gzip, json, re, statistics as st
from collections import defaultdict
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=Path(__file__).resolve().parent.parent / "evidence")
    a = ap.parse_args()
    R = {}
    for line in (a.snapshot / "roster.tsv").read_text().splitlines()[1:]:
        slug, name, *_ = line.split("\t")
        p = name.split()
        R[slug] = dict(full=name, first=p[0], last=p[-1])

    g_tot = g_anchor = g_heard = 0
    kept_sal, unkept_sal = [], []
    perceived_n, kept_n = [], []
    for s, d in R.items():
        f = a.snapshot / "ledgers" / f"{s}.jsonl.gz"
        if not f.exists():
            continue
        ev = [json.loads(l) for l in gzip.open(f, "rt") if l.strip()]
        anchor_sal: dict[str, float] = defaultdict(float)
        heard: set[str] = set()
        kept: set[str] = set()
        for e in ev:
            t, pl = e.get("event_type"), e.get("payload", {})
            if t == "anchor_observed":
                for an in pl.get("anchors", []):
                    name = str(an.get("anchor", "")).lower()
                    sal = float(an.get("salience", 0))
                    for s2, d2 in R.items():
                        if s2 != s and (d2["full"].lower() == name or (d2["first"].lower() in name and d2["last"].lower() in name)):
                            anchor_sal[s2] = max(anchor_sal[s2], sal)
            elif t == "packet_emitted":
                blob = json.dumps(pl).lower()
                for s2, d2 in R.items():
                    if s2 != s and (s2 in blob or d2["full"].lower() in blob):
                        heard.add(s2)
            elif t == "memory_kept":
                note = str(pl.get("note", ""))
                for s2, d2 in R.items():
                    if s2 != s and re.search(r"\b" + re.escape(d2["full"]) + r"\b", note):
                        kept.add(s2)
        perceived = set(anchor_sal) | heard
        perceived_n.append(len(perceived)); kept_n.append(len(kept))
        for peer in kept:
            g_tot += 1
            if peer in anchor_sal:
                g_anchor += 1
            elif peer in heard:
                g_heard += 1
        for peer in perceived:
            (kept_sal if peer in kept else unkept_sal).append(anchor_sal.get(peer, 0.0))

    print("=== SUBSTRATE-ONLY grounding (in-window kept peers, no pen-side address-target) ===")
    print(f"  kept peers total: {g_tot} | via SALIENCE ANCHOR: {g_anchor} ({g_anchor/g_tot:.0%}) | heard-only: {g_heard} ({g_heard/g_tot:.0%}) | ungrounded: {g_tot-g_anchor-g_heard}")
    print("\n=== SELECTIVITY (do keeps prefer HIGH-salience peers?) ===")
    print(f"  mean anchor-salience  KEPT peers: {st.mean(kept_sal):.3f} (n={len(kept_sal)})  |  perceived-NOT-kept: {st.mean(unkept_sal):.3f} (n={len(unkept_sal)})")
    print(f"  coverage: perceived/resident {st.mean(perceived_n):.1f} | kept/resident {st.mean(kept_n):.1f} | keep-of-perceived {sum(kept_n)/sum(perceived_n):.0%}")
    print("\nNOTE: window-bounded (~2h snapshot). 'grounded' here = perceived this window; keeps whose")
    print("perception predates the window read as ungrounded, so this UNDER-counts grounding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
