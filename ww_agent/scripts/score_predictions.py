#!/usr/bin/env python3
"""Score a resident's afterimages against what actually happened (Major 51, Phase 4a).

Pure measurement over the ledger — trains nothing, changes nothing. Answers:
do this resident's predictions anticipate its world?

    python scripts/score_predictions.py familiar/cinder        # one resident
    python scripts/score_predictions.py familiar/*/            # several
    python scripts/score_predictions.py familiar/maker --worst 8

The triad to watch over runtime:
  miss       — surprise on a feature it CLAIMED (wrong where it spoke). lower = better.
  blindspot  — surprise on a feature it did NOT claim (silent where it should have spoken).
  silent%    — afterimages that claimed nothing. a mind drifting toward the DARK ROOM
               shows miss falling while silent% climbs (predicting less to be wrong less).
               genuine learning shows miss AND blindspot falling while silent% stays low.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.runtime.ledger import load_runtime_events  # noqa: E402
from src.runtime.prediction import derive_prediction_scores, summarize_prediction_quality  # noqa: E402


def _report(mem_dir: Path, worst: int) -> None:
    events = load_runtime_events(mem_dir)
    s = summarize_prediction_quality(events)
    name = mem_dir.parent.name if mem_dir.name == "memory" else mem_dir.name
    if not s.get("afterimages"):
        print(f"\n=== {name} ===  no afterimages cast yet")
        return
    print(f"\n=== {name} ===  {s['afterimages']} afterimages  ·  {s['spoke']} spoke  ·  mean {s['mean_claims']} claims each")
    print(f"  miss       {s['mean_miss']:.4f}   (surprise where it spoke — lower is better)")
    print(f"  blindspot  {s['mean_blindspot']:.4f}   (surprise where it was silent)")
    print(f"  clean      {s['clean_fraction']*100:.0f}%   of speaking afterimages had nothing they claimed violated")
    print(f"  silent     {s['silent_fraction']*100:.0f}%   claimed nothing (dark-room indicator)")
    if worst:
        scores = sorted(derive_prediction_scores(events), key=lambda x: -x["miss"])[:worst]
        if scores and scores[0]["miss"] > 0:
            print(f"  worst misses:")
            for sc in scores:
                if sc["miss"] <= 0:
                    break
                print(f"    {sc['cast_ts'][:19]}  miss={sc['miss']:.3f}  claimed={sc['claimed_n']}  blindspot={sc['blindspot']:.3f}")


def main() -> None:
    worst = 0
    skip = set()
    if "--worst" in sys.argv:
        i = sys.argv.index("--worst")
        worst = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 5
        skip = {i, i + 1}
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
        _report(mem, worst)


if __name__ == "__main__":
    main()
