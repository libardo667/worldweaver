"""Prediction scoring: was the afterimage any good? (Major 51, Phase 4a)

The pulse casts an afterimage — a top-down prediction the substrate is then
surprised against (substrate.py / salience.py). Until now nothing ever *scored*
that prediction: surprise re-accumulated as arousal and the afterimage that
earned it was never graded. This is the missing measurement — the precondition
for any model that LEARNS to predict (Major 51, Rung 3). You cannot do gradient
descent on a signal you do not compute.

It is pure derive over the existing ledger (``afterimage_cast`` vs
``surprise_observed``). It trains nothing and changes no live behaviour. It only
answers one empirical question: do the resident's predictions anticipate its
world, or are they decaying noise?

Two error directions, both read straight off the ledger:

- **MISS** — surprise on a feature the afterimage *claimed*. It predicted some
  feature at some intensity and reality still diverged there. The prediction was
  wrong where it spoke.
- **BLINDSPOT** — surprise on a feature the afterimage *did not* claim, during
  its watch. Something it should have anticipated and didn't. The prediction was
  silent where it should have spoken.

A good predictor drives both toward zero. But MISS alone is not the objective:
the **dark-room** failure (Major 51, Rung 3 risk) drives MISS to zero by never
claiming anything — a prediction that says nothing is never wrong. So MISS is
always read against BLINDSPOT and against ``silent_fraction`` (afterimages that
claimed nothing). That triad is what makes the learning objective well-posed
rather than a trap: predict *more* and *better*, not *less*.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.runtime.ledger import load_runtime_events
from src.runtime.salience import SURPRISE_FLOOR

# An afterimage is "on watch" from when it is cast until it has decayed to ~1/8 of
# its initial intensity — three half-lives. Surprise within that window is what it
# was responsible for predicting; surprise after it has faded is not its to answer.
AFTERIMAGE_LIFETIMES = 3.0


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split the ledger into the cast predictions and the observed surprises."""
    afterimages: list[dict[str, Any]] = []
    surprises: list[dict[str, Any]] = []
    for event in events:
        etype = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if etype == "afterimage_cast":
            features = payload.get("features")
            if not isinstance(features, dict) or not features:
                continue
            cast_dt = _parse_dt(payload.get("cast_ts")) or _parse_dt(event.get("ts"))
            if cast_dt is None:
                continue
            scope = str(payload.get("scope") or "here").strip() or "here"
            claimed = {(scope, str(tag).strip()) for tag in features if str(tag).strip()}
            afterimages.append(
                {
                    "pulse_id": str(payload.get("pulse_id") or "").strip(),
                    "cast_dt": cast_dt,
                    "half_life": _coerce_float(payload.get("half_life")) or 0.0,
                    "confidence": _coerce_float(payload.get("confidence")),
                    "claimed": claimed,
                }
            )
        elif etype == "surprise_observed":
            obs_dt = _parse_dt(payload.get("observed_ts")) or _parse_dt(event.get("ts"))
            feats = payload.get("features")
            if obs_dt is None or not isinstance(feats, list):
                continue
            parsed: list[tuple[str, str, float]] = []
            for f in feats:
                if not isinstance(f, dict):
                    continue
                scope = str(f.get("scope") or "here").strip() or "here"
                tag = str(f.get("tag") or "").strip()
                delta = _coerce_float(f.get("delta"))
                if tag and delta is not None:
                    parsed.append((scope, tag, delta))
            if parsed:
                surprises.append({"obs_dt": obs_dt, "features": parsed})
    surprises.sort(key=lambda s: s["obs_dt"])
    return afterimages, surprises


def derive_prediction_scores(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Grade each cast afterimage against the surprise observed during its watch.

    For every ``afterimage_cast``, look at the ``surprise_observed`` traces that
    fell inside its lifetime window and split their surprise into MISS (on a
    feature this afterimage claimed) and BLINDSPOT (on a feature it did not).
    Returns one score per afterimage, oldest first. Pure read; writes nothing.
    """
    afterimages, surprises = _collect(events)
    scores: list[dict[str, Any]] = []
    for ai in afterimages:
        t0 = ai["cast_dt"]
        h = ai["half_life"]
        window_end = t0.timestamp() + AFTERIMAGE_LIFETIMES * h if h > 0 else None
        claimed = ai["claimed"]

        miss_total = miss_n = 0
        miss_total_f = 0.0
        blind_total_f = 0.0
        blind_n = 0
        traces_in_window = 0
        for s in surprises:
            ts = s["obs_dt"].timestamp()
            if ts < t0.timestamp():
                continue
            if window_end is not None and ts > window_end:
                continue
            traces_in_window += 1
            for scope, tag, delta in s["features"]:
                if (scope, tag) in claimed:
                    miss_total_f += delta
                    miss_n += 1
                else:
                    blind_total_f += delta
                    blind_n += 1
        miss = round(miss_total_f / miss_n, 4) if miss_n else 0.0
        blindspot = round(blind_total_f / blind_n, 4) if blind_n else 0.0
        scores.append(
            {
                "pulse_id": ai["pulse_id"],
                "cast_ts": t0.isoformat(),
                "claimed_n": len(claimed),
                "confidence": ai["confidence"],
                "half_life": h,
                "miss": miss,  # mean surprise on a CLAIMED feature (wrong where it spoke)
                "blindspot": blindspot,  # mean surprise on an UNCLAIMED feature (silent where it should have spoken)
                "miss_events": miss_n,
                "blindspot_events": blind_n,
                "traces_in_window": traces_in_window,
                "clean": miss < SURPRISE_FLOOR,  # nothing it claimed was violated above the noise floor
            }
        )
    return scores


def summarize_prediction_quality(events: list[dict[str, Any]]) -> dict[str, Any]:
    """A corpus-level read of how good a resident's predictions are.

    The triad that matters: ``mean_miss`` (wrong where it spoke), ``mean_blindspot``
    (silent where it should have spoken), and ``silent_fraction`` (afterimages
    that claimed nothing at all). A mind sliding toward the dark room shows
    ``mean_miss`` falling while ``silent_fraction`` climbs — predicting less to be
    wrong less. A mind genuinely learning shows MISS and BLINDSPOT both falling
    while ``silent_fraction`` stays low.
    """
    scores = derive_prediction_scores(events)
    n = len(scores)
    if n == 0:
        return {"afterimages": 0}
    claimed = [s for s in scores if s["claimed_n"] > 0]
    silent = n - len(claimed)
    speaking_misses = [s["miss"] for s in claimed]
    blinds = [s["blindspot"] for s in scores]
    clean = [s for s in claimed if s["clean"]]
    return {
        "afterimages": n,
        "spoke": len(claimed),
        "silent_fraction": round(silent / n, 4),
        "mean_claims": round(sum(s["claimed_n"] for s in scores) / n, 3),
        "mean_miss": round(sum(speaking_misses) / len(speaking_misses), 4) if speaking_misses else 0.0,
        "mean_blindspot": round(sum(blinds) / n, 4),
        "clean_fraction": round(len(clean) / len(claimed), 4) if claimed else 0.0,
    }


def score_predictions(memory_dir: Path) -> dict[str, Any]:
    """Live convenience: summarize prediction quality from a resident's ledger."""
    return summarize_prediction_quality(load_runtime_events(memory_dir))
