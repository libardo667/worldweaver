#!/usr/bin/env python3
"""lexical_count.py — recompute the arm-C A/B lexical table from the committed (gzipped) ledgers.

Cold-verifiable: no embedder, no network, no local shards needed. Reads the ledgers committed alongside
this script. This is the recompute path for FINDINGS.md — run it and check the numbers match.

    python3 research/runs/2026-06-08-armC-ab/analysis/lexical_count.py
"""
import glob
import gzip
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
LED = os.path.normpath(os.path.join(HERE, "..", "ledgers"))


def _events(arm):
    for f in glob.glob(os.path.join(LED, arm, "*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for ln in fh:
                try:
                    yield json.loads(ln)
                except json.JSONDecodeError:
                    continue


def analyze(arm):
    speaks, kinds, person = [], Counter(), 0
    for e in _events(arm):
        if e.get("event_type") == "pulse_act_emitted":
            p = e.get("payload", {})
            kinds[p.get("kind")] += 1
            if p.get("kind") == "speak" and p.get("body"):
                speaks.append(str(p["body"]).strip())
                if p.get("target") and str(p.get("target")).lower() not in ("city", "__city__"):
                    person += 1
    n = len(speaks) or 1
    topic = sum(1 for x in speaks if re.search(r"\b(weight|load|frame|bearing|fourteenth|covenant|the break)\b", x, re.I))
    tmpl = sum(1 for x in speaks if re.match(r"\s*(i'm here|i'm in|i read)\b", x, re.I))
    openers = Counter(" ".join(x.split()[:3]).lower() for x in speaks)
    return dict(acts=sum(kinds.values()), speaks=len(speaks), kinds=dict(kinds), person=person,
                topic=100 * topic / n, tmpl=100 * tmpl / n, div=len(openers) / n, top=openers.most_common(3))


for label, arm in (("arcon  (ON / varied)", "arcon"), ("arcoff (OFF/ shared)", "arcoff")):
    r = analyze(arm)
    print(f"{label}: acts={r['acts']} speaks={r['speaks']} person-addressed={r['person']}")
    print(f"   topic-monoculture: {r['topic']:.1f}%   templated opener (I'm here/I read): {r['tmpl']:.1f}%   distinct-opener/speaks: {r['div']:.2f}")
    print(f"   act-kinds: {r['kinds']}")
    print(f"   top openers: {r['top']}")
print("\nRead: arm C swapped the opener template (relocated, not reduced); topic monoculture severe in both arms;")
print("act-kind diversified (ON has more write/move); effect-on-register = null.")
