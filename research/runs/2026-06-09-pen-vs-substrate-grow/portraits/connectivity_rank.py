#!/usr/bin/env python3
"""Rank all 16 residents by connectivity — pins BOTH ends of the swap A/B on ONE axis (round-9 fix).

The composite connectivity axis = (reciprocated dyads, strong dyads, in-degree, in-mass). The swap A/B
takes the two EXTREMES of this single axis: ISOLATE = composite minimum (thinnest own-substrate → by the
loop logic, self migrated LEAST out of the pen → predicted MOST swap-exposed), HUB = composite maximum
(richest own-substrate). NOTE (round-9 cold review): the hub by this axis is **Ari Rosenbaum, NOT Amir** —
earlier prose mixed axes (it named the in-mass maximum, Amir, the hub, while the isolate was the composite
minimum). One axis; both ends from it.

Cold-reproducible; resolve-or-flag counting (full name, or cohort-unique first name; ambiguous bare names
dropped). Run with `--snapshot` pointed at the **D2 freeze** (the state the swap departs from), not the
maturation-time snapshot.
"""
import argparse, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm(x):
    return re.sub(r"[\s_\-]+", " ", str(x or "").strip().lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=HERE / "evidence", help="dir with kept_memory/ + roster.tsv (use the D2-checkpoint for the swap-from state)")
    snap = ap.parse_args().snapshot
    R = {}
    for line in (snap / "roster.tsv").read_text().splitlines()[1:]:
        slug, name, home = (line.split("\t") + ["", "", ""])[:3]
        R[slug] = dict(name=name, home=home)
    firsts = {}
    for s, d in R.items():
        firsts.setdefault(norm(d["name"]).split(" ")[0], []).append(s)
    B = {s: norm(" ".join(json.loads(l).get("note", "") for l in (snap / "kept_memory" / f"{s}.jsonl").open() if l.strip())) for s in R}

    def W(a, b):
        disp = norm(R[b]["name"]); n = len(re.findall(r"\b" + re.escape(disp) + r"\b", B[a]))
        fn = disp.split(" ")[0]
        if len(firsts[fn]) == 1:
            n = max(n, len(re.findall(r"\b" + re.escape(fn) + r"\b", B[a])))
        return n

    rows = []
    for s in R:
        keeps = sum(1 for l in (snap / "kept_memory" / f"{s}.jsonl").open() if l.strip())
        outd = sum(1 for x in R if x != s and W(s, x) > 0)
        ind = sum(1 for x in R if x != s and W(x, s) > 0)
        recip = sum(1 for x in R if x != s and W(s, x) > 0 and W(x, s) > 0)
        strong = sum(1 for x in R if x != s and W(s, x) >= 3 and W(x, s) >= 3)
        inmass = sum(W(x, s) for x in R if x != s)
        rows.append((s, R[s]["home"], keeps, outd, ind, recip, strong, inmass))
    rows.sort(key=lambda r: (r[5], r[6], r[4], r[7]))  # composite axis: recip, strong, in-degree, in-mass
    print(f"snapshot: {snap}")
    print(f"{'resident':18}{'home':16}{'keeps':>6}{'out':>4}{'in':>4}{'recip':>6}{'strong':>7}{'in-mass':>8}")
    for r in rows:
        print(f"{R[r[0]]['name']:18}{r[1]:16}{r[2]:>6}{r[3]:>4}{r[4]:>4}{r[5]:>6}{r[6]:>7}{r[7]:>8}")
    iso, hub = rows[0], rows[-1]
    print(f"\nISOLATE (control)  = composite MIN: {R[iso[0]]['name']:16} — {iso[5]} recip, {iso[6]} strong, in-deg {iso[4]}, in-mass {iso[7]}.")
    print(f"HUB (treatment)    = composite MAX: {R[hub[0]]['name']:16} — {hub[5]} recip, {hub[6]} strong, in-deg {hub[4]}, in-mass {hub[7]}.")
    print("(A/B = the two extremes of this ONE axis. Per the round-9 fix, do NOT substitute the in-mass max for the hub.)")


if __name__ == "__main__":
    raise SystemExit(main())
