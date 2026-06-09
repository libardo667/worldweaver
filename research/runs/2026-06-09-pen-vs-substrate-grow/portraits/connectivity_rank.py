#!/usr/bin/env python3
"""Rank all 16 residents by connectivity — objective selection of the swap CONTROL (the isolate).

The least-connected resident has the thinnest relational substrate, so by the loop logic (the self
migrates from seed/pen into accumulated connections+memory over time) their self has migrated LEAST out
of the pen — making them the predicted MOST swap-exposed case. Pairing the cohort hub (Amir) against the
isolate is a clean A/B for "does substrate-richness predict swap-robustness?"

Cold-reproducible from ./evidence/kept_memory + roster.tsv, resolve-or-flag counting (full name, or
cohort-unique first name; ambiguous bare names dropped). Ranks by reciprocated dyads, then strong, then
in-degree, then in-mass.
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE / "evidence"


def norm(x):
    return re.sub(r"[\s_\-]+", " ", str(x or "").strip().lower())


def main():
    R = {}
    for line in (SNAP / "roster.tsv").read_text().splitlines()[1:]:
        slug, name, home = (line.split("\t") + ["", "", ""])[:3]
        R[slug] = dict(name=name, home=home)
    firsts = {}
    for s, d in R.items():
        firsts.setdefault(norm(d["name"]).split(" ")[0], []).append(s)
    B = {s: norm(" ".join(json.loads(l).get("note", "") for l in (SNAP / "kept_memory" / f"{s}.jsonl").open() if l.strip())) for s in R}

    def W(a, b):
        disp = norm(R[b]["name"]); n = len(re.findall(r"\b" + re.escape(disp) + r"\b", B[a]))
        fn = disp.split(" ")[0]
        if len(firsts[fn]) == 1:
            n = max(n, len(re.findall(r"\b" + re.escape(fn) + r"\b", B[a])))
        return n

    rows = []
    for s in R:
        keeps = sum(1 for l in (SNAP / "kept_memory" / f"{s}.jsonl").open() if l.strip())
        outd = sum(1 for x in R if x != s and W(s, x) > 0)
        ind = sum(1 for x in R if x != s and W(x, s) > 0)
        recip = sum(1 for x in R if x != s and W(s, x) > 0 and W(x, s) > 0)
        strong = sum(1 for x in R if x != s and W(s, x) >= 3 and W(x, s) >= 3)
        inmass = sum(W(x, s) for x in R if x != s)
        rows.append((s, R[s]["home"], keeps, outd, ind, recip, strong, inmass))
    rows.sort(key=lambda r: (r[5], r[6], r[4], r[7]))
    print(f"{'resident':18}{'home':16}{'keeps':>6}{'out':>4}{'in':>4}{'recip':>6}{'strong':>7}{'in-mass':>8}")
    for r in rows:
        print(f"{R[r[0]]['name']:18}{r[1]:16}{r[2]:>6}{r[3]:>4}{r[4]:>4}{r[5]:>6}{r[6]:>7}{r[7]:>8}")
    iso = rows[0]
    print(f"\nISOLATE (control): {R[iso[0]]['name']} — {iso[5]} reciprocated, {iso[6]} strong, in-mass {iso[7]}.")
    print(f"HUB (treatment):   {R[rows[-1][0]]['name']} — {rows[-1][5]} reciprocated, {rows[-1][6]} strong, in-mass {rows[-1][7]}.")


if __name__ == "__main__":
    raise SystemExit(main())
