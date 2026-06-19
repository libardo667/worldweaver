# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

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

**Drive-weighting — the price on boring.** ``silent_fraction`` catches the
*vacuous* dark room (claim nothing). It does NOT catch the *dull-world* dark
room: an afterimage that perfectly predicts a room where nothing happens scores
clean — flawless prediction of furniture. Raw surprise can't tell skilled
prediction from dull-world prediction, because it never asks whether what was
predicted *mattered*. So an optional ``weights`` map (tag → soul-resonance, from
the drive vector — ``tag_mattering`` builds it) lets surprise about a thing the
resident is *drawn to* count for more than surprise about the furniture. With it
we get ``claim_mattering`` (did the afterimage even claim things that matter?) —
the instrument that distinguishes a clean predictor from a bored one. The
principled objective is drive-weighted, not raw: predict well *about what you
care about*. Without that, "getting better at predicting" and "drifting toward
the dull quiet room" are the same gradient.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.runtime.ledger import load_runtime_events
from src.runtime.salience import ANCHOR_SCOPE, SURPRISE_FLOOR

# An afterimage is "on watch" from when it is cast until it has decayed to ~1/8 of
# its initial intensity — three half-lives. Surprise within that window is what it
# was responsible for predicting; surprise after it has faded is not its to answer.
AFTERIMAGE_LIFETIMES = 3.0

# A predicted anchor counts as "held" if it stayed at least this salient in the
# realized anchor snapshots over the afterimage's watch.
ANCHOR_HIT_FLOOR = 0.15


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


def derive_prediction_scores(events: list[dict[str, Any]], *, weights: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """Grade each cast afterimage against the surprise observed during its watch.

    For every ``afterimage_cast``, look at the ``surprise_observed`` traces that
    fell inside its lifetime window and split their surprise into MISS (on a
    feature this afterimage claimed) and BLINDSPOT (on a feature it did not).
    Returns one score per afterimage, oldest first. Pure read; writes nothing.

    ``weights`` (tag → soul-resonance in ``[0, 1]``, from ``tag_mattering``) adds
    the drive-weighted view: ``claim_mattering`` (how much the afterimage's chosen
    claims matter to this resident) and ``weighted_miss`` / ``weighted_blindspot``
    (surprise scaled by how much its feature mattered). Absent, those fields are
    ``None`` and behaviour is the raw, unweighted scorer.
    """

    def w(tag: str) -> float:
        return float(weights.get(tag, 0.0)) if weights is not None else 1.0

    afterimages, surprises = _collect(events)
    scores: list[dict[str, Any]] = []
    for ai in afterimages:
        t0 = ai["cast_dt"]
        h = ai["half_life"]
        window_end = t0.timestamp() + AFTERIMAGE_LIFETIMES * h if h > 0 else None
        claimed = ai["claimed"]

        miss_n = 0
        miss_total_f = 0.0
        miss_weighted_f = 0.0
        blind_total_f = 0.0
        blind_weighted_f = 0.0
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
                    miss_weighted_f += delta * w(tag)
                    miss_n += 1
                else:
                    blind_total_f += delta
                    blind_weighted_f += delta * w(tag)
                    blind_n += 1
        miss = round(miss_total_f / miss_n, 4) if miss_n else 0.0
        blindspot = round(blind_total_f / blind_n, 4) if blind_n else 0.0
        # claim_mattering: how much, on average, this resident is drawn to the
        # features the afterimage chose to claim. LOW = it predicted furniture
        # (dull-world dark room); HIGH = it spoke about what it cares about.
        claim_mattering = round(sum(w(tag) for _, tag in claimed) / len(claimed), 4) if (weights is not None and claimed) else None
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
                "claim_mattering": claim_mattering,
                "weighted_miss": round(miss_weighted_f / miss_n, 4) if (weights is not None and miss_n) else None,
                "weighted_blindspot": round(blind_weighted_f / blind_n, 4) if (weights is not None and blind_n) else None,
            }
        )
    return scores


async def tag_mattering(drive_vector: Any, tags: list[str]) -> dict[str, float]:
    """For each feature tag, how much this resident's soul is drawn to it — the
    drive vector's ``resonance`` magnitude over the humanized tag. The weight map
    that turns raw surprise into drive-weighted surprise. Embeds each distinct tag
    once. With an empty/absent drive vector every weight is 0.0 (the scorer then
    reports drive-weighted fields as zero, never crashing)."""
    weights: dict[str, float] = {}
    for tag in {str(t).strip() for t in tags if str(t).strip()}:
        try:
            res = await drive_vector.resonance(tag.replace("_", " "))
            weights[tag] = round(float(res.get("magnitude") or 0.0), 4)
        except Exception:
            weights[tag] = 0.0
    return weights


def summarize_prediction_quality(events: list[dict[str, Any]], *, weights: dict[str, float] | None = None) -> dict[str, Any]:
    """A corpus-level read of how good a resident's predictions are.

    The triad that matters: ``mean_miss`` (wrong where it spoke), ``mean_blindspot``
    (silent where it should have spoken), and ``silent_fraction`` (afterimages
    that claimed nothing at all). A mind sliding toward the *vacuous* dark room
    shows ``mean_miss`` falling while ``silent_fraction`` climbs — predicting less
    to be wrong less.

    With ``weights`` (from ``tag_mattering``) the *dull-world* dark room becomes
    visible too: ``mean_claim_mattering`` is how much the resident's predictions
    are even about things it cares about. A bored mind predicting furniture scores
    a high ``clean_fraction`` but a LOW ``mean_claim_mattering`` — clean and empty.
    Genuine skill is clean AND mattering. That gap is where the dark room hides
    from the raw scorer.
    """
    scores = derive_prediction_scores(events, weights=weights)
    n = len(scores)
    if n == 0:
        return {"afterimages": 0}
    claimed = [s for s in scores if s["claimed_n"] > 0]
    silent = n - len(claimed)
    speaking_misses = [s["miss"] for s in claimed]
    blinds = [s["blindspot"] for s in scores]
    clean = [s for s in claimed if s["clean"]]
    out = {
        "afterimages": n,
        "spoke": len(claimed),
        "silent_fraction": round(silent / n, 4),
        "mean_claims": round(sum(s["claimed_n"] for s in scores) / n, 3),
        "mean_miss": round(sum(speaking_misses) / len(speaking_misses), 4) if speaking_misses else 0.0,
        "mean_blindspot": round(sum(blinds) / n, 4),
        "clean_fraction": round(len(clean) / len(claimed), 4) if claimed else 0.0,
    }
    if weights is not None:
        matterings = [s["claim_mattering"] for s in claimed if s["claim_mattering"] is not None]
        wmiss = [s["weighted_miss"] for s in claimed if s["weighted_miss"] is not None]
        out["mean_claim_mattering"] = round(sum(matterings) / len(matterings), 4) if matterings else 0.0
        out["mean_weighted_miss"] = round(sum(wmiss) / len(wmiss), 4) if wmiss else 0.0
    return out


def score_predictions(memory_dir: Path) -> dict[str, Any]:
    """Live convenience: summarize prediction quality from a resident's ledger."""
    return summarize_prediction_quality(load_runtime_events(memory_dir))


# --- the anchor lane (Major 51 granularity): predictions about concrete things ---


def derive_anchor_scores(events: list[dict[str, Any]], *, weights: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """Grade each anchor-scoped afterimage against the realized anchor snapshots.

    Anchors are predicted in their own scope and scored offline, never touching the
    arousal rhythm. For each ``afterimage_cast`` with ``scope == "anchors"``, an
    anchor it claimed "held" if it stayed salient in the ``anchor_observed``
    snapshots over the afterimage's watch. ``weights`` (anchor → soul-resonance, via
    ``tag_mattering``) adds ``claim_mattering`` — which, unlike over the five flat
    drives, genuinely varies, because anchors are this resident's own.
    """

    def w(tag: str) -> float:
        return float(weights.get(tag, 0.0)) if weights is not None else 1.0

    casts: list[dict[str, Any]] = []
    snaps: list[dict[str, Any]] = []
    for event in events:
        etype = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if etype == "afterimage_cast" and str(payload.get("scope") or "").strip() == ANCHOR_SCOPE:
            feats = payload.get("features")
            if not isinstance(feats, dict) or not feats:
                continue
            cdt = _parse_dt(payload.get("cast_ts")) or _parse_dt(event.get("ts"))
            if cdt is None:
                continue
            claimed = {str(t).strip(): float(v) for t, v in feats.items() if str(t).strip() and _coerce_float(v) is not None}
            casts.append({"pulse_id": str(payload.get("pulse_id") or "").strip(), "cast_dt": cdt, "half_life": _coerce_float(payload.get("half_life")) or 0.0, "claimed": claimed})
        elif etype == "anchor_observed":
            odt = _parse_dt(payload.get("observed_ts")) or _parse_dt(event.get("ts"))
            anchors = payload.get("anchors")
            if odt is None or not isinstance(anchors, list):
                continue
            field: dict[str, float] = {}
            for a in anchors:
                if isinstance(a, dict):
                    nm = str(a.get("anchor") or "").strip()
                    sv = _coerce_float(a.get("salience"))
                    if nm and sv is not None:
                        field[nm] = sv
            snaps.append({"obs_dt": odt, "field": field})
    snaps.sort(key=lambda s: s["obs_dt"])

    scores: list[dict[str, Any]] = []
    for c in casts:
        t0 = c["cast_dt"]
        h = c["half_life"]
        end = t0.timestamp() + AFTERIMAGE_LIFETIMES * h if h > 0 else None
        claimed = c["claimed"]
        realized: dict[str, float] = {}
        for s in snaps:
            ts = s["obs_dt"].timestamp()
            if ts < t0.timestamp() or (end is not None and ts > end):
                continue
            for tag in claimed:
                realized[tag] = max(realized.get(tag, 0.0), s["field"].get(tag, 0.0))
        misses = [abs(intensity - realized.get(tag, 0.0)) for tag, intensity in claimed.items()]
        hits = sum(1 for tag in claimed if realized.get(tag, 0.0) >= ANCHOR_HIT_FLOOR)
        scores.append(
            {
                "pulse_id": c["pulse_id"],
                "cast_ts": t0.isoformat(),
                "claimed_n": len(claimed),
                "anchor_miss": round(sum(misses) / len(misses), 4) if misses else 0.0,
                "hit_rate": round(hits / len(claimed), 4) if claimed else 0.0,
                "claim_mattering": round(sum(w(t) for t in claimed) / len(claimed), 4) if (weights is not None and claimed) else None,
            }
        )
    return scores


def summarize_anchor_prediction(events: list[dict[str, Any]], *, weights: dict[str, float] | None = None) -> dict[str, Any]:
    """Corpus read of the anchor lane: how well a resident predicts the concrete
    things its world is made of, and (with ``weights``) how much those predictions
    are about what it cares about."""
    scores = derive_anchor_scores(events, weights=weights)
    n = len(scores)
    if n == 0:
        return {"anchor_afterimages": 0}
    out = {
        "anchor_afterimages": n,
        "mean_claims": round(sum(s["claimed_n"] for s in scores) / n, 3),
        "mean_anchor_miss": round(sum(s["anchor_miss"] for s in scores) / n, 4),
        "mean_hit_rate": round(sum(s["hit_rate"] for s in scores) / n, 4),
    }
    if weights is not None:
        cms = [s["claim_mattering"] for s in scores if s["claim_mattering"] is not None]
        out["mean_claim_mattering"] = round(sum(cms) / len(cms), 4) if cms else 0.0
    return out
