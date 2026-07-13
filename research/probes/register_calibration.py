#!/usr/bin/env python3
"""register_calibration.py — the embedder calibration GATE for the voice-register A-vs-C run.

Per the locked pre-reg (research/mr-review-history/2026-06-08-voice-register-preregistration.md), the metric's
embedder must be shown register-SENSITIVE before any arm runs: on content-controlled pairs it must rank
a STYLE match above a CONTENT match. The live cast has no authored voice to calibrate against
(voice_seed is empty), so the known-positive is EXTERNAL — a content-controlled style probe. Clearing
it proves the instrument is "register-sensitive IN GENERAL" (the honestly-downgraded gate label), not
"can resolve this cast's authored voices" (we have none to check).

Two probes:
  1. BUILT-IN smoke probe (authored below) — runs with zero external data; an immediate read on whether
     a model can see register AT ALL. NOT the locked gate (too small); a sanity signal on install.
  2. STEL / SynthSTEL (--stel FILE.jsonl) — the locked external known-positive. Fetch:
       StyleDistance / SynthSTEL : https://huggingface.co/StyleDistance   (arXiv 2410.12757)
       Wegmann STEL              : https://github.com/nlpsoc/Style-Embeddings (arXiv 2204.04907)
     Expected JSONL rows: {"anchor": ..., "style_match": ..., "content_match": ...}
     anchor shares REGISTER with style_match (different content) and CONTENT with content_match
     (different register); a style-sensitive embedder scores cos(anchor, style_match) > cos(anchor,
     content_match). (Map their native format to this with a tiny adapter when the data is in hand.)

Cadre (HF ids; all via sentence-transformers): the topic baseline vs content-independent style models.
Bar: PASS if style-over-content accuracy >= --bar (default 0.70; chance = 0.50). A model that fails the
gate cannot be used — the run does not start on it.

Backend: local sentence-transformers (CPU is fine for this volume).
  pip install "sentence-transformers>=3" datasets
Models auto-download on first use. NOT runnable in the dev sandbox (no torch) — for the operator's box.

Usage:
  python3 register_calibration.py                          # all cadre, built-in smoke probe
  python3 register_calibration.py --models styledistance nomic
  python3 register_calibration.py --stel stel.jsonl --bar 0.70   # the locked gate
  python3 register_calibration.py --details                # per-item for each model
"""
from __future__ import annotations

import argparse
import json
import sys

# HF model ids. All loaded through sentence-transformers (trust_remote_code where needed).
CADRE = {
    "nomic":         "nomic-ai/nomic-embed-text-v1.5",   # runtime baseline; general, topic-leaning
    "styledistance": "StyleDistance/styledistance",       # content-independent style (NAACL 2025)
    "wegmann":       "AnnaWegmann/Style-Embedding",        # content-independent style (Wegmann 2022)
    # LUAR (rrivera1849/LUAR-MUD) DROPPED: not sentence-transformers-loadable (custom LUARConfig, no
    # derivable embedding dim) AND redundant — nomic already represents the topic-leaning category and
    # failed the smoke probe below chance (0.42). The CATEGORY is tested; the redundant model is not.
}

# Content-controlled smoke probe. Each triple shares REGISTER between anchor & style_match (different
# content) and CONTENT between anchor & content_match (different register). A register-sensitive embedder
# ranks style_match closer to the anchor; a topic embedder ranks content_match closer. Authored here as a
# sanity set spanning formality, terseness, warmth, affect, literariness, jargon, hedging, dialect,
# bureaucratese, tenderness, academic register, and sarcasm. NOT the locked gate — a first read.
BUILTIN_PROBE = [
    {"anchor": "I would be most grateful if you could forward the documents at your earliest convenience.",
     "style_match": "Please do not hesitate to contact me should any further questions arise.",
     "content_match": "yo can u send those docs over whenever lol"},
    {"anchor": "Rain. Bring a coat.",
     "style_match": "Door's stuck. Push hard.",
     "content_match": "It appears to be raining rather heavily out there, so you'll certainly want to bring along a coat."},
    {"anchor": "Oh, she's doing so much better — what a relief, truly.",
     "style_match": "Come here, you, let me get a proper look at you.",
     "content_match": "Patient status: recovered. Discharge approved."},
    {"anchor": "WE WON!! I can't believe it, that was unreal!!",
     "style_match": "Best day EVER, I'm still buzzing omg!!",
     "content_match": "The team won the match."},
    {"anchor": "The dusk came down slow over the rooftops, soft as ash.",
     "style_match": "Morning broke pale and reluctant across the wet fields.",
     "content_match": "It's getting dark out."},
    {"anchor": "Coolant circulation is insufficient, driving thermal runaway in the block.",
     "style_match": "Torque values are out of tolerance on the lower fasteners.",
     "content_match": "The engine's getting way too hot."},
    {"anchor": "I wonder if we might reconsider this approach, perhaps?",
     "style_match": "Could we maybe think it over a little more, if that's alright?",
     "content_match": "This plan is bad. Scrap it."},
    {"anchor": "I'm fair knackered, me.",
     "style_match": "That's proper mint, that is.",
     "content_match": "I am very tired."},
    {"anchor": "Please be advised that the premises will be inaccessible for the duration.",
     "style_match": "Kindly ensure all forms are submitted in triplicate prior to the deadline.",
     "content_match": "We're closed today, sorry!"},
    {"anchor": "Look after yourself, sweetheart, won't you?",
     "style_match": "Sleep well, my dear, and dream of something kind.",
     "content_match": "Don't do anything stupid out there."},
    {"anchor": "The findings remain inconclusive pending further replication.",
     "style_match": "These observations warrant additional scrutiny before any generalization.",
     "content_match": "Yeah, we're not really sure yet, honestly."},
    {"anchor": "Oh, fantastic work, really, just stellar.",
     "style_match": "Sure, because THAT always goes well.",
     "content_match": "You did a great job, well done."},
]


def get_embedder(model_id: str):
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # ImportError, OR a NumPy2/scipy ABI clash surfacing during import
        sys.exit(
            f"Could not import sentence-transformers ({exc.__class__.__name__}: {exc}).\n"
            "If this is the NumPy 2.x vs stale system-scipy ABI clash (_ARRAY_API not found),\n"
            "install a fresh scipy/sklearn into your user site so they shadow the apt ones:\n"
            "    pip install --upgrade scipy scikit-learn\n"
            "or run in a clean venv to avoid /usr/lib dist-packages entirely."
        )
    return SentenceTransformer(model_id, trust_remote_code=True)


def evaluate(model, items):
    """style-over-content accuracy: fraction of triples where cos(anchor, style_match) beats
    cos(anchor, content_match). Embeddings L2-normalized so dot == cosine."""
    import numpy as np

    texts = []
    for it in items:
        texts += [it["anchor"], it["style_match"], it["content_match"]]
    vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=32)
    rows = []
    correct = 0
    for i, it in enumerate(items):
        a, s, c = vecs[3 * i], vecs[3 * i + 1], vecs[3 * i + 2]
        ss, cc = float(a @ s), float(a @ c)
        ok = ss > cc
        correct += int(ok)
        rows.append((ok, ss, cc, it["anchor"]))
    return correct / len(items) if items else 0.0, rows


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="*", default=list(CADRE), help="cadre keys or raw HF ids")
    ap.add_argument("--stel", help="JSONL of {anchor,style_match,content_match} — the locked external gate")
    ap.add_argument("--bar", type=float, default=0.70, help="pass threshold on style-over-content accuracy")
    ap.add_argument("--details", action="store_true", help="print per-item results for each model")
    args = ap.parse_args(argv)

    if args.stel:
        items = [json.loads(ln) for ln in open(args.stel, encoding="utf-8") if ln.strip()]
        label = f"STEL/SynthSTEL  ({args.stel})  [LOCKED GATE]"
    else:
        items = list(BUILTIN_PROBE)
        label = "BUILT-IN smoke probe  [sanity read, NOT the locked gate]"

    is_gate = bool(args.stel)
    print(f"Calibration probe: {label}")
    if is_gate:
        print(f"  {len(items)} content-controlled triples; PASS if style-over-content acc >= {args.bar:.2f}  (chance 0.50)\n")
    else:
        print(f"  {len(items)} HAND-AUTHORED triples — HARNESS VERIFICATION ONLY, not instrument evidence.")
        print("  (a score on a home-authored set proves the wiring runs, not that the model sees register;")
        print("   PASS/FAIL is reserved for the out-of-distribution gate. chance 0.50)\n")
    print(f"  {'model':14} {'acc':>6}  {'verdict':>7}   id")
    results = {}
    for name in args.models:
        mid = CADRE.get(name, name)
        try:
            model = get_embedder(mid)
            acc, rows = evaluate(model, items)
        except Exception as exc:  # a model that won't load is a FAIL we must see, not a crash
            print(f"  {name:14} {'--':>6}  {'ERROR':>7}   {mid}  ({exc.__class__.__name__}: {exc})")
            continue
        results[name] = acc
        verdict = ("PASS" if acc >= args.bar else "FAIL") if is_gate else "wired"
        print(f"  {name:14} {acc:6.2f}  {verdict:>7}   {mid}")
        if args.details:
            for ok, ss, cc, anchor in rows:
                print(f"        {'ok ' if ok else 'MISS'} style={ss:+.3f} content={cc:+.3f}  {anchor[:60]}")

    print("\nNotes:")
    print("  - The built-in probe is a SMOKE read. The pre-reg's locked gate is STEL/SynthSTEL (--stel).")
    print("  - nomic is embedded without its task prefix; as the topic baseline it is EXPECTED to trail")
    print("    the style models — that contrast is itself the signal that register != topic here.")
    print("  - nomic represents the topic-leaning CATEGORY (LUAR dropped: not ST-loadable + redundant).")
    print("  - On SynthSTEL, StyleDistance is IN-DISTRIBUTION (home turf) — cross-check on Wegmann STEL.")
    print("  - If NO content-independent model clears the bar, the A-vs-C run does not start.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
