#!/usr/bin/env python3
"""peer_register_check.py — THE matched-to-target gate (Mr. Review round 8 + parallax diagnostic).

The whole instrument-validation chain certified embedders against COARSE register contrasts (toxicity,
formality, synthetic feature-bundles) — never the contrast the experiment turns on: PEER-LEVEL register
among individual speakers. This runs the cheap direct test the chain skipped, using the one
peer-register known-positive already in the repo: the historical hand-authored residents
(ww_agent/residents/*/identity/IDENTITY.md), whose `Voice:` blocks were deliberately written to differ
at peer granularity (the retiree's clipped finality vs the cook's portion-brevity, etc.).

QUESTION: can the embedder SEPARATE souls authored to differ in voice?
  - clean separation + stable  -> the metric family HAS the resolution the experiment needs -> proceed.
  - "exploratory fog"          -> embedding-separability is the wrong family for peer-register, and no
                                  coarse gate would have revealed it. Reconsider the family.

METHOD (borrowed from parallax/js/embedding/diagnostics.js, measured in the ORIGINAL embedding space —
rotation-invariant, not a projection):
  1. per-soul CENTROID of its authored voice-line embeddings; inter-soul cosine-distance MATRIX
     (parallax: computeDiscSimilarityMatrix).
  2. SEPARATION: leave-one-out nearest-centroid accuracy (is each voice line closest to its OWN soul's
     centroid?), scored REAL vs a soul-label-shuffle null (z). Chance = 1 / n_souls.
  3. STABILITY: resample voice lines per soul, recompute each soul's nearest-neighbour map, average
     neighbour-overlap across resamples (parallax: computeProjectionStability / neighborOverlap) ->
     stable (>=0.75) / mixed (>=0.45) / exploratory fog (<0.45). Reliability, distinct from validity.

CAVEATS (honest): the authored Voice blocks are SHORT (4-6 lines/soul) and this is a DIFFERENT cast than
the live doula-seeded residents — so this tests the INSTRUMENT'S RESOLUTION CEILING on deliberately
distinct voices, a necessary condition. Stable separation here doesn't prove the live cast individuates;
FOG here proves the instrument can't resolve peer-register even when it's authored to exist.

Usage:
  pip install "sentence-transformers>=3"
  python3 peer_register_check.py
  python3 peer_register_check.py --residents /abs/path/to/residents --models styledistance wegmann
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import sys

CADRE = {
    "styledistance": "StyleDistance/styledistance",
    "wegmann":       "AnnaWegmann/Style-Embedding",
    "nomic":         "nomic-ai/nomic-embed-text-v1.5",
}


def get_embedder(model_id):
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        sys.exit(f"sentence-transformers not importable ({exc.__class__.__name__}: {exc}). "
                 "pip install 'sentence-transformers>=3' (+ pip install --upgrade scipy scikit-learn if NumPy2 ABI)")
    return SentenceTransformer(model_id, trust_remote_code=True)


def load_voices(residents_dir):
    """soul -> [authored voice utterances], parsed from IDENTITY.md '- **Voice:**' lines."""
    voices = {}
    for d in sorted(os.listdir(residents_dir)):
        if d.startswith("_"):
            continue  # skip _template (its Voice line is a placeholder instruction)
        idp = os.path.join(residents_dir, d, "identity", "IDENTITY.md")
        if not os.path.isfile(idp):
            continue
        for line in open(idp, encoding="utf-8"):
            if line.startswith("- **Voice:**"):
                raw = line.split("**Voice:**", 1)[-1].strip()
                utts = [u.strip().strip("\"'") for u in raw.split(",") if u.strip()]
                if utts:
                    voices[d] = utts
                break
    return voices


def _centroids(V, idx, souls):
    import numpy as np
    cent = {}
    for s in souls:
        c = V[idx[s]].mean(0)
        cent[s] = c / (float(np.linalg.norm(c)) + 1e-9)
    return cent


def separation(V, labels, souls, idx, draws=500, seed=12345):
    """leave-one-out nearest-centroid accuracy vs a soul-label-shuffle null."""
    import numpy as np

    def acc_for(lab_list):
        ix = {s: [i for i, l in enumerate(lab_list) if l == s] for s in souls}
        cent = _centroids(V, ix, souls)
        correct = 0
        for i, lab in enumerate(lab_list):
            own = [k for k in ix[lab] if k != i]
            own_c = cent[lab] if not own else (V[own].mean(0) / (float(np.linalg.norm(V[own].mean(0))) + 1e-9))
            best, bs = -2.0, None
            for s in souls:
                c = own_c if s == lab else cent[s]
                sim = float(V[i] @ c)
                if sim > best:
                    best, bs = sim, s
            correct += int(bs == lab)
        return correct / len(lab_list)

    real = acc_for(labels)
    rng = random.Random(seed)
    null = []
    for _ in range(draws):
        sh = labels[:]
        rng.shuffle(sh)
        null.append(acc_for(sh))
    mean, sd = statistics.fmean(null), statistics.pstdev(null)
    z = (real - mean) / sd if sd > 0 else 0.0
    return real, mean, z, 1.0 / len(souls)


def stability(V, idx, souls, B=30, drop=0.34, seed=12345):
    """resample voice lines per soul; how stable is each soul's nearest-neighbour map? (parallax)"""
    rng = random.Random(seed)

    def nnmap(ix):
        cent = _centroids(V, ix, souls)
        nn = {}
        for s in souls:
            ranked = sorted(((float(cent[s] @ cent[o]), o) for o in souls if o != s), reverse=True)
            nn[s] = [o for _, o in ranked[:2]]
        return nn

    base = nnmap(idx)
    overlaps = []
    for _ in range(B):
        sub = {}
        ok = True
        for s in souls:
            ids = idx[s][:]
            keep = max(2, int(round(len(ids) * (1 - drop))))
            rng.shuffle(ids)
            sub[s] = sorted(ids[:keep])
            if len(sub[s]) < 1:
                ok = False
        if not ok:
            continue
        m = nnmap(sub)
        ov = []
        for s in souls:
            a, b = set(base[s]), set(m[s])
            ov.append(len(a & b) / max(len(a), len(b), 1))
        overlaps.append(statistics.fmean(ov))
    score = statistics.fmean(overlaps) if overlaps else None
    label = "exploratory fog" if score is None else ("stable" if score >= 0.75 else "mixed" if score >= 0.45 else "exploratory fog")
    return score, label


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--residents", default=os.path.normpath(os.path.join(here, "..", "residents")))
    ap.add_argument("--models", nargs="*", default=["styledistance", "wegmann"])
    args = ap.parse_args(argv)

    import numpy as np

    voices = load_voices(args.residents)
    voices = {s: u for s, u in voices.items() if len(u) >= 2}  # need >=2 lines for leave-one-out
    souls = sorted(voices)
    if len(souls) < 3:
        sys.exit(f"need >=3 souls with >=2 authored voice lines; found {len(souls)} in {args.residents}")
    n_lines = sum(len(voices[s]) for s in souls)
    print(f"Peer-register self-check: {len(souls)} authored souls, {n_lines} voice lines, {args.residents}")
    print(f"  souls: {', '.join(souls)}\n")

    for name in args.models:
        mid = CADRE.get(name, name)
        try:
            model = get_embedder(mid)
            lines, labels = [], []
            for s in souls:
                for u in voices[s]:
                    lines.append(u)
                    labels.append(s)
            V = model.encode(lines, normalize_embeddings=True, convert_to_numpy=True, batch_size=32)
            idx = {s: [i for i, l in enumerate(labels) if l == s] for s in souls}
        except Exception as exc:
            print(f"  {name:14} ERROR ({exc.__class__.__name__}: {exc})  {mid}")
            continue

        real, null_mean, z, chance = separation(V, labels, souls, idx)
        stab_score, stab_label = stability(V, idx, souls)
        verdict = "RESOLVES peer-register" if (z > 2 and real > 2 * chance) else ("exploratory fog" if stab_label == "exploratory fog" else "WEAK / inconclusive")
        print(f"  === {name} ({mid}) ===")
        print(f"    nearest-centroid accuracy {real:.2f}  vs chance {chance:.2f}  vs shuffle-null {null_mean:.2f}  -> z {z:+.1f}")
        print(f"    stability: {stab_label}" + (f" ({stab_score*100:.0f}% neighbour overlap)" if stab_score is not None else ""))
        print(f"    -> {verdict}\n")

    print("reading: z>2 AND acc>>chance AND stable  -> instrument resolves authored peer-voices, proceed.")
    print("         exploratory fog / acc~chance      -> embedding-separability can't see peer-register;")
    print("                                              reconsider the metric family (no coarse gate would show this).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
