#!/usr/bin/env python3
"""Score a resident's afterimages against what actually happened (Major 51, Phase 4a).

Pure measurement over the ledger — trains nothing, changes nothing. Answers:
do this resident's predictions anticipate its world?

    python scripts/score_predictions.py familiar/cinder        # one resident
    python scripts/score_predictions.py familiar/*/            # several
    python scripts/score_predictions.py familiar/maker --worst 8
    python scripts/score_predictions.py familiar/cinder --drive # drive-weighted (needs WW_EMBEDDING_URL)

The triad to watch over runtime:
  miss       — surprise on a feature it CLAIMED (wrong where it spoke). lower = better.
  blindspot  — surprise on a feature it did NOT claim (silent where it should have spoken).
  silent%    — afterimages that claimed nothing. a mind drifting toward the *vacuous*
               DARK ROOM shows miss falling while silent% climbs (predicting less to be
               wrong less). genuine learning shows miss AND blindspot falling, silent% low.

With --drive (the price on boring): surprise is weighted by how much each feature
matters to THIS resident's soul, exposing the *dull-world* dark room that silent%
can't see —
  mattering  — did it predict things the soul cares about? low + high clean = clean-but-
               empty: flawless prediction of furniture, the dark room's quiet signature.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.runtime.ledger import load_runtime_events  # noqa: E402
from src.runtime.prediction import derive_prediction_scores, summarize_prediction_quality  # noqa: E402


async def _drive_weights(resident_dir: Path, events: list) -> dict | None:
    """Soul-resonance weight per feature tag, from this resident's drive vector.
    Returns None (raw scoring) if no embedder is configured or it can't be reached."""
    import os

    url = os.environ.get("WW_EMBEDDING_URL", "").strip()
    if not url:
        print("  (--drive: no WW_EMBEDDING_URL set — showing raw scores only)")
        return None
    from src.identity.loader import IdentityLoader
    from src.runtime.drive import DriveVector, RemoteEmbedder
    from src.runtime.prediction import tag_mattering

    tags = set()
    for e in events:
        p = e.get("payload", {})
        if e.get("event_type") == "afterimage_cast":
            tags.update((p.get("features") or {}).keys())
        elif e.get("event_type") == "surprise_observed":
            tags.update(f.get("tag") for f in (p.get("features") or []))
    emb = RemoteEmbedder(base_url=url, api_key=os.environ.get("WW_EMBEDDING_KEY", "ollama"), model=os.environ.get("WW_EMBEDDING_MODEL", "nomic-embed-text"))
    try:
        canon, growth = IdentityLoader.load_canonical_and_growth(resident_dir)
        dv = await DriveVector.build(embedder=emb, constitution=canon, growth=growth)
        return await tag_mattering(dv, [t for t in tags if t])
    except Exception as exc:
        print(f"  (--drive: embedder unreachable — {type(exc).__name__}; raw scores only)")
        return None
    finally:
        await emb.close()


def _report(mem_dir: Path, worst: int, weights: dict | None) -> None:
    events = load_runtime_events(mem_dir)
    s = summarize_prediction_quality(events, weights=weights)
    name = mem_dir.parent.name if mem_dir.name == "memory" else mem_dir.name
    if not s.get("afterimages"):
        print(f"\n=== {name} ===  no afterimages cast yet")
        return
    print(f"\n=== {name} ===  {s['afterimages']} afterimages  ·  {s['spoke']} spoke  ·  mean {s['mean_claims']} claims each")
    print(f"  miss       {s['mean_miss']:.4f}   (surprise where it spoke — lower is better)")
    print(f"  blindspot  {s['mean_blindspot']:.4f}   (surprise where it was silent)")
    print(f"  clean      {s['clean_fraction']*100:.0f}%   of speaking afterimages had nothing they claimed violated")
    print(f"  silent     {s['silent_fraction']*100:.0f}%   claimed nothing (vacuous dark-room indicator)")
    if "mean_claim_mattering" in s:
        print(f"  mattering  {s['mean_claim_mattering']:.4f}   did it predict things THIS soul cares about? (low + clean = dull-world dark room)")
        print(f"  wt-miss    {s['mean_weighted_miss']:.4f}   miss, weighted by how much the feature mattered")
    if worst:
        scores = sorted(derive_prediction_scores(events, weights=weights), key=lambda x: -x["miss"])[:worst]
        if scores and scores[0]["miss"] > 0:
            print(f"  worst misses:")
            for sc in scores:
                if sc["miss"] <= 0:
                    break
                print(f"    {sc['cast_ts'][:19]}  miss={sc['miss']:.3f}  claimed={sc['claimed_n']}  blindspot={sc['blindspot']:.3f}")


def main() -> None:
    import asyncio

    worst = 0
    skip = set()
    if "--worst" in sys.argv:
        i = sys.argv.index("--worst")
        worst = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 5
        skip = {i, i + 1}
    drive = "--drive" in sys.argv
    args = [a for j, a in enumerate(sys.argv[1:], start=1) if not a.startswith("--") and j not in skip]
    if not args:
        print(__doc__)
        return
    for raw in args:
        base = Path(raw)
        mem = base if base.name == "memory" else base / "memory"
        if not mem.is_dir():
            print(f"\n=== {raw} ===  no memory/ dir")
            continue
        weights = asyncio.run(_drive_weights(mem.parent, load_runtime_events(mem))) if drive else None
        _report(mem, worst, weights)


if __name__ == "__main__":
    main()
