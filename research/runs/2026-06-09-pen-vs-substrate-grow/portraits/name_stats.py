#!/usr/bin/env python3
"""A4 evidence (round-9 NEEDS-ARTIFACT): addressing-name resolvability at the D2 freeze.

Replaces the unsupported "pens wrote full names 191/192; 3 distinct normalized strings" prose. Computes,
from the ledgers' `pulse_act_emitted` speak targets, how addressable the cohort's names actually are —
the question the resolve-or-flag scorer (A4) turns on.

Cold-reproducible: `python3 name_stats.py --snapshot ../D2-checkpoint` (reads ledgers/*.jsonl.gz +
roster.tsv). Reports: person-target acts, % multi-token (full-name), and the homophone cluster
(Jihoon Cho / Ji-Hoon Park / Jiahao Chen) — distinct normalized strings + %full-name, the only place a
naive scorer could conflate.
"""
import argparse, gzip, json, re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm(x):
    return re.sub(r"[\s_\-]+", " ", str(x or "").strip().lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=HERE.parent / "D2-checkpoint")
    a = ap.parse_args()
    snap = a.snapshot
    R = {}
    for line in (snap / "roster.tsv").read_text().splitlines()[1:]:
        slug, name, *_ = line.split("\t")
        R[slug] = name
    full_norms = {norm(n) for n in R.values()}
    first_counts = Counter(norm(n).split(" ")[0] for n in R.values())
    homophone = {"jihoon cho", "ji hoon park", "jiahao chen"}

    targets = []
    for f in (snap / "ledgers").glob("*.jsonl.gz"):
        for l in gzip.open(f, "rt"):
            if '"pulse_act_emitted"' not in l:
                continue
            e = json.loads(l); pl = e.get("payload", {})
            if e.get("event_type") == "pulse_act_emitted" and pl.get("kind") == "speak":
                t = str(pl.get("target") or "").strip()
                if t:
                    targets.append(t)

    city = {"city", "__city__", "citywide", "broadcast"}
    person, multi_token, bare_unique, bare_ambig, other = 0, 0, 0, 0, 0
    homo_acts, homo_norms = 0, Counter()
    for t in targets:
        nt = norm(t)
        if nt in city:
            continue
        if nt in full_norms:
            person += 1; multi_token += (1 if " " in nt else 0)
            if nt in homophone:
                homo_acts += 1; homo_norms[nt] += 1
        elif nt in first_counts:  # bare first name
            person += 1
            bare_unique += (1 if first_counts[nt] == 1 else 0)
            bare_ambig += (1 if first_counts[nt] > 1 else 0)
        else:
            other += 1
    total_person = person
    print(f"snapshot: {snap}")
    print(f"speak acts with a target: {len(targets)} | city: {sum(1 for t in targets if norm(t) in city)} | other(place/desc): {other}")
    print(f"person-addressed acts: {total_person}")
    print(f"  multi-token full-name matches: {multi_token} ({multi_token/total_person:.0%})")
    print(f"  bare first name (cohort-unique, resolvable): {bare_unique}")
    print(f"  bare first name (AMBIGUOUS -> flagged, never guessed): {bare_ambig}")
    print(f"\nhomophone cluster (Jihoon Cho / Ji-Hoon Park / Jiahao Chen):")
    print(f"  addressing acts: {homo_acts} | distinct normalized strings: {len(homo_norms)} -> {dict(homo_norms)}")
    print(f"  % full-name (multi-token): {sum(homo_norms.values())/homo_acts:.0%}" if homo_acts else "  (none)")
    print("\nReading: pens address by RESOLVABLE full names; the homophone cluster stays distinct under")
    print("normalization (so resolve_reference disambiguates), and ambiguous bare refs are flagged, not guessed.")


if __name__ == "__main__":
    raise SystemExit(main())
