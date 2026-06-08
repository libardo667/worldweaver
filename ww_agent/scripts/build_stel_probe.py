#!/usr/bin/env python3
"""build_stel_probe.py — assemble the LOCKED calibration probe from SynthSTEL for
register_calibration.py.

SynthSTEL (HF: StyleDistance/synthstel) is stored as PAIRS, one row per content-controlled contrast:
  positive       — a sentence demonstrating a style feature   (style F, content C)
  negative       — the SAME content C in a CONTRASTING style
  feature / feature_clean — the style dimension (40 / 38 values)

The calibration harness wants STEL-or-Content TRIPLETS. We build them per row:
  anchor        = positive                                   (style F, content C)
  content_match = negative                                   (same content C, contrasting style)
  style_match   = another row's positive in the SAME feature (style F, DIFFERENT content)
A register-sensitive embedder scores  cos(anchor, style_match) > cos(anchor, content_match).

CIRCULARITY CAVEAT (read before banking the gate): SynthSTEL is StyleDistance's OWN benchmark family.
Even the held-out TEST split is in-distribution for StyleDistance — it has a home-field advantage here,
so a StyleDistance pass on SynthSTEL is NOT an independent result. The independent cross-check is
Wegmann's STEL (github nlpsoc/Style-Embeddings, different construction, TSV), where StyleDistance is
out-of-distribution — run that as a second probe before locking the instrument. SynthSTEL IS a fair
gate for the OTHER models (nomic, Wegmann did not train on it).

Usage:
  pip install datasets
  python3 build_stel_probe.py --split test --out synthstel_test.jsonl
  python3 register_calibration.py --stel synthstel_test.jsonl --bar 0.70
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="test", choices=["test", "train"], help="test = held out from StyleDistance training")
    ap.add_argument("--out", default="synthstel_test.jsonl")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--feature-col", default="feature_clean", help="group by feature_clean (38) or feature (40)")
    args = ap.parse_args(argv)

    try:
        from datasets import load_dataset
    except Exception as exc:
        sys.exit(f"datasets not importable ({exc.__class__.__name__}: {exc}).  pip install datasets")

    rows = list(load_dataset("StyleDistance/synthstel", split=args.split))
    rng = random.Random(args.seed)

    by_feat = defaultdict(list)
    for i, r in enumerate(rows):
        by_feat[r[args.feature_col]].append(i)

    out, skipped = [], 0
    for i, r in enumerate(rows):
        pool = [j for j in by_feat[r[args.feature_col]] if j != i]
        if not pool:
            skipped += 1  # singleton feature: no same-style different-content partner
            continue
        j = rng.choice(pool)
        out.append({
            "anchor": r["positive"],
            "style_match": rows[j]["positive"],   # same feature-style, DIFFERENT content
            "content_match": r["negative"],        # same content, contrasting style
            "feature": r[args.feature_col],
        })

    with open(args.out, "w", encoding="utf-8") as fh:
        for o in out:
            fh.write(json.dumps(o, ensure_ascii=False) + "\n")

    print(f"wrote {len(out)} triplets ({skipped} skipped: singleton features) -> {args.out}")
    print(f"split={args.split}  features={len(by_feat)}  seed={args.seed}")
    if out:
        s = out[0]
        print("sample triplet:")
        print(f"  anchor       : {s['anchor'][:80]}")
        print(f"  style_match  : {s['style_match'][:80]}   (feature '{s['feature']}', diff content)")
        print(f"  content_match: {s['content_match'][:80]}   (same content, diff style)")
    print("\nNOTE: StyleDistance trained on SynthSTEL's family — its pass here is in-distribution, not")
    print("independent. Cross-check on Wegmann STEL (out-of-distribution for StyleDistance) before locking.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
