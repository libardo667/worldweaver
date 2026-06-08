#!/usr/bin/env python3
"""register_construct_check.py — does the cadre even SHARE a register axis? (Mr. Review round 6)

The SynthSTEL gate showed StyleDistance 0.94 and Wegmann 0.22 (BELOW chance) on the SAME triplets.
That is not "two instruments with different sensitivity to one axis" — it may be "two instruments
measuring different constructs." If the style models do not agree on WHICH items are more
style-than-content, then "survives instrument substitution" (the robustness lock) is unsatisfiable BY
CONSTRUCTION, and no new benchmark (option B / GYAFC) repairs it. This check decides that BEFORE
building B — using data already in hand, no gated corpus. It is the prior question.

Per triplet, each model's STYLE MARGIN = cos(anchor, style_match) - cos(anchor, content_match)
(>0 means the style pull beat the content pull on that item). We correlate the margin VECTORS across
models (Pearson + Spearman):
  - positive & meaningful (e.g. r > ~0.3)  -> shared axis, differing threshold/scale -> option B is
                                              signal; proceed to a substitute OOD probe.
  - ~0 or negative                         -> NO shared axis -> STOP: rewrite the robustness lock; a
                                              cadre that doesn't share a construct cannot cross-validate,
                                              and the separability metric family needs reconsidering
                                              before any benchmark choice means anything.

Usage:
  python3 register_construct_check.py --stel synthstel_test.jsonl
  python3 register_construct_check.py --stel synthstel_test.jsonl --models styledistance wegmann nomic
"""
from __future__ import annotations

import argparse
import json
import sys

CADRE = {
    "nomic":         "nomic-ai/nomic-embed-text-v1.5",
    "styledistance": "StyleDistance/styledistance",
    "wegmann":       "AnnaWegmann/Style-Embedding",
}


def get_embedder(model_id):
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        sys.exit(
            f"Could not import sentence-transformers ({exc.__class__.__name__}: {exc}).\n"
            "pip install 'sentence-transformers>=3'  (and if NumPy2/scipy ABI: pip install --upgrade scipy scikit-learn)"
        )
    return SentenceTransformer(model_id, trust_remote_code=True)


def margins(model_id, items):
    """Per-triplet style margin = cos(anchor, style_match) - cos(anchor, content_match)."""
    import numpy as np

    model = get_embedder(model_id)
    texts = []
    for it in items:
        texts += [it["anchor"], it["style_match"], it["content_match"]]
    v = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=32)
    out = []
    for i in range(len(items)):
        a, s, c = v[3 * i], v[3 * i + 1], v[3 * i + 2]
        out.append(float(a @ s) - float(a @ c))
    return np.array(out)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stel", required=True, help="JSONL triplets {anchor,style_match,content_match}")
    ap.add_argument("--models", nargs="*", default=["styledistance", "wegmann"])
    args = ap.parse_args(argv)

    from scipy.stats import pearsonr, spearmanr

    items = [json.loads(ln) for ln in open(args.stel, encoding="utf-8") if ln.strip()]
    print(f"Construct-agreement check: {len(items)} triplets, models {args.models}")
    print("(do the instruments agree on WHICH items are style>content? — the question B presupposes)\n")

    M = {}
    for name in args.models:
        mid = CADRE.get(name, name)
        try:
            m = margins(mid, items)
        except Exception as exc:
            print(f"  {name:14} ERROR ({exc.__class__.__name__}: {exc})  {mid}")
            continue
        M[name] = m
        print(f"  {name:14} mean style-margin {m.mean():+.4f}   style-wins fraction {float((m > 0).mean()):.2f}   {mid}")

    print("\n  per-triplet margin correlation (shared axis?):")
    names = list(M)
    if len(names) < 2:
        print("    need >=2 loaded models to correlate.")
        return 1
    verdict_lines = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            r, rp = pearsonr(M[a], M[b])
            rho, sp = spearmanr(M[a], M[b])
            print(f"    {a} vs {b}:  Pearson r={r:+.3f} (p={rp:.1e})   Spearman rho={rho:+.3f} (p={sp:.1e})")
            verdict_lines.append((a, b, r, rho))

    print("\n  reading:")
    print("    r > ~0.3 positive   -> shared axis, differing threshold -> option B (substitute OOD probe) is signal.")
    print("    r ~ 0 or negative   -> NO shared axis -> STOP: the robustness lock is void as written; a cadre")
    print("                           that doesn't share a construct can't cross-validate. Reconsider the")
    print("                           separability metric family before choosing any benchmark.")
    # the decisive pair for THIS question is the two content-independent style models
    for a, b, r, rho in verdict_lines:
        if {a, b} == {"styledistance", "wegmann"}:
            call = "SHARED AXIS (proceed to B)" if r > 0.3 else ("NO SHARED AXIS (stop, rewrite lock)" if r < 0.1 else "AMBIGUOUS (borderline; treat as no-go pending a second set)")
            print(f"\n  decisive pair styledistance vs wegmann: r={r:+.3f} -> {call}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
