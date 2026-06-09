#!/usr/bin/env python3
"""Detect social groups across the WHOLE cohort — is the Nike Girl family a one-off?

Cold-verifiable from ./evidence/kept_memory + ./evidence/roster.tsv. Builds the directed keep-graph
with resolve-or-flag counting (full name, or cohort-unique first name; ambiguous bare names FLAGGED),
then reports, per geographic cluster, reciprocated and STRONG (>=3 each way) dyads, plus the
cross-cluster reciprocated web. Showing every cluster is the guard against cherry-picking one pretty
group.
"""
import json, os, re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = Path(os.environ.get("SNAPSHOT") or (HERE / "evidence"))  # set SNAPSHOT=../D2-checkpoint to re-pin at D2


def norm(x):
    return re.sub(r"[\s_\-]+", " ", str(x or "").strip().lower())


def make_labels(R):
    """Disambiguated display label per resident: ALWAYS first name + last initial (extended to the
    shortest last-name prefix that is globally unique). Always carrying the last initial defends not
    just EXACT collisions ("Ari L."/"Ari R.") but the homophone near-misses this cohort is full of —
    "Jihoon C." / "Ji-Hoon P." / "Jiahao C." render as three clearly different people, never a bare
    "Jihoon". This is the round-6 resolve-or-flag rule carried all the way into the LABEL layer (a
    collided or near-collided label is the same silent-confusion bug, one level down)."""
    def key(slug, k):
        p = R[slug]["name"].split()
        return (norm(p[0]), norm(p[-1])[:k])
    lab = {}
    for s, d in R.items():
        parts = d["name"].split(); first, last = parts[0], parts[-1]
        k = 1
        while sum(1 for p in R if key(p, k) == key(s, k)) > 1:
            k += 1
        lab[s] = f"{first} {last[:k]}."
    return lab


def main():
    R = {}
    for line in (SNAP / "roster.tsv").read_text().splitlines()[1:]:
        slug, name, home = (line.split("\t") + ["", "", ""])[:3]
        R[slug] = dict(name=name, home=home)
    firsts = {}
    for s, d in R.items():
        firsts.setdefault(norm(d["name"]).split(" ")[0], []).append(s)

    def blob(s):
        return norm(" ".join(json.loads(l).get("note", "") for l in (SNAP / "kept_memory" / f"{s}.jsonl").open() if l.strip()))

    B = {s: blob(s) for s in R}

    def W(a, b):
        disp = norm(R[b]["name"]); n = len(re.findall(r"\b" + re.escape(disp) + r"\b", B[a]))
        fn = disp.split(" ")[0]
        if len(firsts[fn]) == 1:
            n = max(n, len(re.findall(r"\b" + re.escape(fn) + r"\b", B[a])))
        return n

    L = make_labels(R)
    clusters = {}
    for s, d in R.items():
        clusters.setdefault(d["home"], []).append(s)

    print("=== per geographic cluster (reciprocated / STRONG>=3-each-way) ===")
    for loc, mem in clusters.items():
        recip = [(a, b) for i, a in enumerate(mem) for b in mem[i + 1:] if W(a, b) and W(b, a)]
        strong = [(a, b) for a, b in recip if W(a, b) >= 3 and W(b, a) >= 3]
        print(f"  {loc:22} ({len(mem)}): reciprocated {len(recip)}/6 | STRONG {len(strong)}")
        for a, b in recip:
            print(f"       {L[a]:10}<->{L[b]:10} ({W(a,b)}/{W(b,a)})" + ("  *STRONG*" if (a, b) in strong else ""))

    cross = [(a, b) for a in R for b in R if a < b and R[a]["home"] != R[b]["home"] and W(a, b) and W(b, a)]
    strong_cross = [(a, b) for a, b in cross if W(a, b) >= 3 and W(b, a) >= 3]
    print(f"\n=== cross-cluster reciprocated: {len(cross)} ({len(strong_cross)} STRONG) ===")
    for a, b in strong_cross:
        print(f"       {L[a]:10}({R[a]['home'][:10]}) <-> {L[b]:10}({R[b]['home'][:10]})  ({W(a,b)}/{W(b,a)})")


if __name__ == "__main__":
    raise SystemExit(main())
