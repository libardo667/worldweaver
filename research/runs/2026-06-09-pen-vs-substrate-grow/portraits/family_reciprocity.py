#!/usr/bin/env python3
"""Recompute the 'Nike Girl family' reciprocity matrix — cold-verifiable from ./evidence/kept_memory.

Counts, per resident, how many kept memories name each other family member. Uses the SAME
resolve-or-flag logic as the experiment scorer (src/runtime/naming.resolve_reference, inlined here so
this runs without the agent installed): a unique normalized FULL name resolves; a unique normalized
FIRST name resolves (collision-free in this quartet — only one Amir/Layla/Phuong/Minh); collisions
would be flagged, not guessed. This is exactly why a naive FULL-name-only count undercounts Minh->Amir
(Minh writes "Amir", not "Amir Mansour") — the bug the round-6 review flagged, here in the analysis tool.
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE / "evidence" / "kept_memory"
FAMILY = ["amir_mansour", "layla_haddad", "phuong_tran", "minh_nguyen"]


def norm(s: str) -> str:
    return re.sub(r"[\s_\-]+", " ", str(s or "").strip().lower())


def load_full_roster() -> dict:
    """slug -> display name, ALL residents — ambiguity must be judged against the WHOLE cohort, not a
    convenient subset (resolving 'Layla' inside a 4-person family falsely makes it unique; in the full
    16 there are two Laylas, so bare 'Layla' is ambiguous and must be FLAGGED, not credited)."""
    R = {}
    for line in (HERE / "evidence" / "roster.tsv").read_text().splitlines()[1:]:
        slug, name, *_ = line.split("\t")
        R[slug] = name
    return R


def main() -> int:
    full = load_full_roster()
    firsts = {}
    for slug, disp in full.items():
        firsts.setdefault(norm(disp).split(" ")[0], []).append(slug)

    def count(blob: str, target_slug: str) -> int:
        nb = norm(blob)
        disp = norm(full[target_slug])
        n = len(re.findall(r"\b" + re.escape(disp) + r"\b", nb))  # full name always resolves
        first = disp.split(" ")[0]
        if len(firsts[first]) == 1:  # bare first name credited ONLY if cohort-unique
            n = max(n, len(re.findall(r"\b" + re.escape(first) + r"\b", nb)))
        return n

    ambiguous = {f for f, ss in firsts.items() if len(ss) > 1}
    print(f"cohort-ambiguous first names (bare ref FLAGGED, full name required): {sorted(ambiguous)}\n")
    print("who keeps about whom (resolve-or-flag against the FULL roster):\n")
    for slug in FAMILY:
        f = SNAP / f"{slug}.jsonl"
        blob = " ".join(json.loads(l).get("note", "") for l in f.open() if l.strip())
        total = sum(1 for l in f.open() if l.strip())
        row = "  ".join(f"{full[s].split()[0]} {full[s].split()[-1][0]}.:{count(blob, s)}" for s in FAMILY if s != slug)
        print(f"  {full[slug]:16} ({total:2} keeps)  ->  {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
