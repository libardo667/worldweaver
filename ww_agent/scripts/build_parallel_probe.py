#!/usr/bin/env python3
"""build_parallel_probe.py — build a construct/OOD probe from any freely-loadable parallel style corpus
(two columns = the SAME content in two registers), with a CONTENT-OVERLAP PRE-CHECK so a near-duplicate
corpus is rejected BEFORE it's trusted as a gate.

WHY THE PRE-CHECK (Mr. Review round 7): ParaDetox failed as a gate because its pairs are near-duplicates
(content_match = a minimal toxic edit of the anchor), so content overlap swamps register and BOTH models
scored ~0.35 style-wins — agreeing while both failing (correlated blindness). A fair gate needs register
difference LARGE relative to content/surface difference. So before trusting any candidate gate corpus,
measure the surface-overlap distribution of its parallel pairs; reject the near-duplicate ones.

Triplet (register-sensitive embedder scores cos(anchor, style_match) > cos(anchor, content_match)):
  anchor        = col_a[i]   (register A, content i)
  content_match = col_b[i]   (SAME content i, register B)        -> the content pull
  style_match   = col_a[j]   (register A, DIFFERENT content j)   -> the style pull

Usage:
  pip install datasets
  # vet a corpus FIRST (no triplets written):
  python3 build_parallel_probe.py --dataset s-nlp/paradetox --col-a en_neutral_comment --col-b en_toxic_comment --overlap-only
  # then build if it passes the vet:
  python3 build_parallel_probe.py --out probe.jsonl --n 400
  python3 register_construct_check.py --stel probe.jsonl
  python3 register_calibration.py --stel probe.jsonl --bar 0.70
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="s-nlp/paradetox")
    ap.add_argument("--split", default="train")
    ap.add_argument("--col-a", default="en_neutral_comment", help="register A (anchor + style_match source)")
    ap.add_argument("--col-b", default="en_toxic_comment", help="register B (content_match source)")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--out", default="paradetox_probe.jsonl")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--overlap-only", action="store_true", help="report the content-overlap pre-check and stop")
    args = ap.parse_args(argv)

    try:
        from datasets import load_dataset
    except Exception as exc:
        sys.exit(f"datasets not importable ({exc.__class__.__name__}: {exc}).  pip install datasets")

    rows = list(load_dataset(args.dataset, split=args.split))
    pairs = []
    for r in rows:
        a = str(r.get(args.col_a) or "").strip()
        b = str(r.get(args.col_b) or "").strip()
        if a and b and len(a) <= 300 and len(b) <= 300:
            pairs.append((a, b))
    if len(pairs) < 4:
        sys.exit(f"too few usable pairs ({len(pairs)}) — check --col-a / --col-b names against the dataset")

    # CONTENT-OVERLAP PRE-CHECK — reject near-duplicate corpora before trusting them as a gate.
    jac = sorted(_jaccard(a, b) for a, b in pairs)
    def _pct(p):
        return jac[min(len(jac) - 1, int(p * len(jac)))]
    med = statistics.median(jac)
    print(f"content-overlap pre-check (token Jaccard between the parallel pair, n={len(pairs)}):")
    print(f"  p10={_pct(0.10):.2f}   median={med:.2f}   p90={_pct(0.90):.2f}")
    if med >= 0.60:
        print("  ** NEAR-DUPLICATE (median Jaccard >= 0.60): content overlap will swamp register — a POOR")
        print("     gate (this is why ParaDetox failed). Use a corpus with substantial register rewrite. **")
    elif med >= 0.35:
        print("  borderline: moderate overlap — usable but watch absolute style-wins on the gate.")
    else:
        print("  good gate shape: low surface overlap = genuine register rewrites, not near-duplicates.")
    if args.overlap_only:
        return 0

    rng = random.Random(args.seed)
    rng.shuffle(pairs)
    n = min(args.n, len(pairs))
    out = []
    for i in range(n):
        a_i, b_i = pairs[i]
        j = rng.randrange(len(pairs))
        while j == i or pairs[j][1] == b_i:   # different content == different register-B source
            j = rng.randrange(len(pairs))
        out.append({
            "anchor": a_i,                 # register A, content i
            "style_match": pairs[j][0],    # register A, DIFFERENT content
            "content_match": b_i,          # SAME content i, register B
            "source": args.dataset,
        })

    with open(args.out, "w", encoding="utf-8") as fh:
        for o in out:
            fh.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(out)} triplets -> {args.out}  (from {args.dataset}:{args.split}, {len(pairs)} usable pairs)")
    if out:
        s = out[0]
        print("sample:")
        print(f"  anchor       : {s['anchor'][:80]}")
        print(f"  style_match  : {s['style_match'][:80]}   (register A, diff content)")
        print(f"  content_match: {s['content_match'][:80]}   (same content, register B)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
