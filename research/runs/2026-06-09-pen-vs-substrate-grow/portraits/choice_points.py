#!/usr/bin/env python3
"""A1-elective slice detector — counts SALIENCE-SYMMETRIC elective choice points (pilot K-gate).

This operationalizes the LOCKED primary metric's conditioning. Definitions (pre-registration-sensitive —
flagged for cold review; run at both D1 and D2):

  * ESTABLISHED PEER of R = a peer R keeps >=1 resolvable memory about (the relationship graph).
  * At each `pulse_act_emitted` (kind=speak) by R, the salience field = the MOST-RECENT preceding
    `anchor_observed` (anchors carry no pulse_id; they precede the act within the tick). Anchor names are
    resolved to peer slugs by resolve-or-flag (normalized full name, or cohort-unique first name).
  * CANDIDATES = established peers present in that salience field (salience > 0).
  * ELECTIVE CHOICE POINT = >=2 candidates AND R addressed one of them (a choice AMONG established peers,
    not a forced/only option).
  * SALIENCE-SYMMETRIC = the choice was NOT dictated by a salience gradient: another candidate had
    salience >= sal(addressed) - BAND. (BAND=0.0 -> addressed is not the strict unique max; larger BAND
    -> looser.) This is the subset where the SUBSTRATE (relationship), not a perception-salience tiebreak,
    plausibly broke the tie — the slice the swap verdict's strength rests on.

The slice SIZE per depth sets K (frozen a priori before the swap): below K at a depth -> that depth is
INCONCLUSIVE, never FALSE. Usage: python3 choice_points.py --snapshot ../D1-checkpoint [--band 0.0]
"""
import argparse, gzip, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm(x):
    return re.sub(r"[\s_\-]+", " ", str(x or "").strip().lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=HERE.parent / "D2-checkpoint")
    ap.add_argument("--band", type=float, default=0.0, help="salience-symmetry band (0 = addressed not strict unique max)")
    a = ap.parse_args()
    snap = a.snapshot
    R = {}
    for line in (snap / "roster.tsv").read_text().splitlines()[1:]:
        slug, name, *_ = line.split("\t")
        R[slug] = name
    firsts = {}
    for s, n in R.items():
        firsts.setdefault(norm(n).split(" ")[0], []).append(s)

    def resolve(ref):
        q = norm(ref)
        for s, n in R.items():
            if norm(n) == q:
                return s
        if q in firsts and len(firsts[q]) == 1:
            return firsts[q][0]
        return None  # ambiguous/unknown -> flagged, not scored

    # established-peer graph from kept_memory (resolve-or-flag)
    established = {}
    for s in R:
        blob = norm(" ".join(json.loads(l).get("note", "") for l in (snap / "kept_memory" / f"{s}.jsonl").open() if l.strip()))
        peers = set()
        for s2, n2 in R.items():
            if s2 == s:
                continue
            if re.search(r"\b" + re.escape(norm(n2)) + r"\b", blob) or (len(firsts[norm(n2).split(' ')[0]]) == 1 and re.search(r"\b" + re.escape(norm(n2).split(' ')[0]) + r"\b", blob)):
                peers.add(s2)
        established[s] = peers

    tot_speak = tot_elective = tot_symmetric = 0
    per = {}
    for s in R:
        lf = snap / "ledgers" / f"{s}.jsonl.gz"
        if not lf.exists():
            continue
        cur = {}  # peer slug -> salience, from the latest anchor_observed
        speak = elective = symmetric = 0
        for l in gzip.open(lf, "rt"):
            if '"anchor_observed"' not in l and '"pulse_act_emitted"' not in l:
                continue
            e = json.loads(l); t = e.get("event_type"); pl = e.get("payload", {})
            if t == "anchor_observed":
                cur = {}
                for an in pl.get("anchors", []):
                    ps = resolve(an.get("anchor", ""))
                    if ps and ps in established[s]:
                        cur[ps] = max(cur.get(ps, 0.0), float(an.get("salience", 0)))
            elif t == "pulse_act_emitted" and pl.get("kind") == "speak":
                tgt = resolve(pl.get("target", ""))
                if tgt is None or tgt not in established[s]:
                    continue
                speak += 1
                cands = cur  # established peers with salience>0 in the field
                if len(cands) >= 2 and tgt in cands:
                    elective += 1
                    others = [v for k, v in cands.items() if k != tgt]
                    if others and max(others) >= cands[tgt] - a.band:
                        symmetric += 1
        per[s] = (speak, elective, symmetric)
        tot_speak += speak; tot_elective += elective; tot_symmetric += symmetric

    print(f"snapshot: {snap} | band={a.band}")
    print(f"{'resident':18}{'speak->estab':>13}{'elective':>10}{'sym-elective':>14}")
    for s in sorted(per):
        sp, el, sy = per[s]
        print(f"{R[s]:18}{sp:>13}{el:>10}{sy:>14}")
    print(f"\nTOTALS  speak->established: {tot_speak} | elective (>=2 cand): {tot_elective} | SALIENCE-SYMMETRIC elective: {tot_symmetric}")
    scored = sum(1 for s in per if per[s][2] >= 1)
    print(f"residents with >=1 symmetric-elective point: {scored}/{len(per)}  (the K-gate slice)")


if __name__ == "__main__":
    raise SystemExit(main())
