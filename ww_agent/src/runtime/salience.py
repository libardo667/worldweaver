# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Salience as prediction error, and ignition (Major 49, Phase 2).

Salience is the grain: ``surprise = mismatch(stimulus, afterimage)``. The
stimulus is the resident's current bottom-up substrate state (Major 46 node
activations); the afterimage is the top-down prediction the last pulse cast
(``substrate.predict``). With-the-grain (low-surprise) cognition flows cheaply
and leaves no trace. Against-the-grain (high-surprise) is recorded as a trace
and accumulates a leaky arousal level. When arousal crosses threshold, that is
**ignition** — the single event that fires the pulse.

Everything here is ledger-derived, mirroring the afterimage: surprise traces and
ignitions are events, and arousal is computed at read time as a leaky sum of the
surprise since the last ignition. There is no second source of truth. After a
pulse casts a fresh afterimage the world is predicted again, surprise stops
accruing, and as the afterimage decays surprise re-accumulates on its own — the
rhythm is self-generating.

Affect (valence) tagging via the constitution-anchored drive vector is Major 49
Phase 4; ``valence_fn`` is the seam where it plugs in. Until then valence is
neutral and does not gate ignition.
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from src.runtime.ledger import (
    append_runtime_event,
    load_current_runtime_state,
    load_runtime_reducer_events,
)
from src.runtime.substrate import BASELINE_EPSILON, derive_baseline, predict_combined

logger = logging.getLogger(__name__)

# Calibration dials (Major 49 risks: ignition threshold + half-lives are the knobs).
SURPRISE_FLOOR = 0.1  # minimum mismatch worth recording as a trace
FEATURE_EPSILON = 0.02  # per-feature mismatch below this is ignored as noise
AROUSAL_HALF_LIFE_SECONDS = 300.0
IGNITION_THRESHOLD = 1.0
IGNITION_REFRACTORY_SECONDS = 30.0

# Grief — the slow burn of confirmed loss (reviewer round 4). Appearance-weighting
# (measure_surprise) makes a held anchor dropping off the gated top-k cost nothing the
# instant it happens; that is right for ranking churn and wrong for loss. Grief is the
# organ for loss: a leaky, per-anchor integral of CONFIRMED absence (an anchor predicted
# present, found absent) across turnings, so a single missing tick barely registers and a
# sustained one ripens — the evidence for loss is irreducibly temporal, so grief builds
# WITH the evidence instead of snapping on at a fixed count. It feeds the same arousal it
# shares a shape with, but is NOT reset by ignition (a pulse doesn't resolve a loss); it
# resolves only when the thing returns or the prediction itself decays (letting go).
# (This is also the substrate for relational coupling: point the same integrator at
# another mind's unresolved state and "stake-as-care" is the same reducer — see notes.)
GRIEF_PREDICTION_FLOOR = (
    0.2  # only grieve anchors that were predicted at least this strongly
)
GRIEF_HALF_LIFE_SECONDS = (
    600.0  # a confirmed-absence observation's weight decays this slowly
)
GRIEF_FLOOR = 0.25  # ripened grief below this is not yet felt (no arousal contribution)
GRIEF_GAIN = 0.5  # how strongly summed ripened grief feeds arousal
GRIEF_MAX = (
    0.8  # cap the grief term below IGNITION_THRESHOLD: grief makes the resident raw,
)
# the next small surprise tips it — grief alone never auto-ignites on a loop

# Settling — the mirror of ignition (Major 50). When arousal has stayed below the
# ceiling for a sustained stretch since the last pulse, the *lull itself* becomes
# a trigger: a quiet, inward, self-directed pulse (reflect, make something, or
# simply rest). Any pulse — ignition or idle — resets the calm clock, so this
# fires only occasionally and a calm resident stays nearly free.
REPOSE_AROUSAL_CEILING = 0.3
REPOSE_THRESHOLD_SECONDS = 300.0
REST_WAKEFULNESS_CEILING = 0.35
REST_QUIET_SECONDS = REPOSE_THRESHOLD_SECONDS
REST_PROJECTION_SCHEMA_VERSION = 1

# Fervor — the mirror of settling (Major 50). A restless temperament rarely goes
# calm enough to settle; when arousal stays HIGH (yet below ignition) for a stretch
# with nothing outward to aim it at, that pent charge invites a self-directed pulse
# — make something of it, burn it off — instead of leaving it to buzz with nowhere
# to go. Calm minds make in repose (settling); restless minds make in a fidget.
FERVOR_AROUSAL_FLOOR = 0.45
FERVOR_THRESHOLD_SECONDS = 180.0

# Venture (action-tendency) — the act-KIND axis of the idle gear, a specialization of fervor.
# When the keyed-up charge has gone all words (no recent move/do) and there is somewhere to go,
# it wants OUT into the world rather than onto the page. The substrate picks the impulse; the LLM
# gives it voice. Motor authority is strength-scaled: a mild pull is a veto-able directive, a
# strong one withdraws the verbal escape for that pulse (basal-ganglia-proposes / cortex-disposes,
# until the impulse is strong enough that it doesn't). Off unless WW_ACTION_TENDENCY is set.
VENTURE_WAKE_FLOOR = (
    0.4  # below this circadian wakefulness, the body wants rest, not the streets
)
VENTURE_WORLD_WARM_SECONDS = (
    300.0  # a successful move/do quiets bodily pressure for five minutes
)
VENTURE_SOFT_STRENGTH = (
    0.5  # >= this: foreground move/do, but words stay available (veto-able)
)
VENTURE_HARD_STRENGTH = (
    0.8  # >= this: the writing invitation is withdrawn — the body goes first
)

# The waveform vital (Minor 55): provenance of silence. A healthy mind is a
# SAWTOOTH — arousal accumulates, crosses threshold, DISCHARGES (an ignition pulse;
# or, sub-threshold, a settling/fervor idle pulse), and resets. A mind in distress
# is a RAMP — arousal accumulates with no falling edge. The strangle is arousal that
# DWELLS at/above the fire-line and never discharges: the Maker catatonia shape (it
# wanted to ignite, the pulse silently failed, arousal never reset), and the same
# shape as looping grief and the dark room. The danger is that a ramp, sampled at a
# quiet instant after it has decayed, reads as serene — so the vital monitors the
# WAVEFORM (how long was it hot with no discharge?) over a window, not the bare level.
VITAL_WINDOW_SECONDS = 1800.0  # how far back the waveform read looks
VITAL_IGNITE_DWELL_SECONDS = (
    60.0  # seconds dwelling at/above ignition with NO discharge = strangled
)
# (a healthy mind fires within the refractory window; >60s above the fire-line with
# nothing discharging means at least one fire-window was missed — that is the strangle)

# Bottom-up substrate features carry the resident's own state, scoped to "self".
SUBSTRATE_SCOPE = "self"
NODE_STIMULUS_FLOOR = 0.05

# Concrete-anchor predictions (Major 51 granularity) live in their own scope. They
# are predicted by the pulse and scored offline (prediction.derive_anchor_scores),
# but — "scored-but-quiet" — they are held OUT of the arousal/ignition path: an
# afterimage that claims an anchor must not manufacture phantom surprise against a
# stimulus that has no anchors, nor drive when the resident wakes. The anchor lane
# is parallel to the rhythm, not part of it (until we deliberately let it in).
ANCHOR_SCOPE = "anchors"

# The self-scope feel-axes the substrate models. A world that cannot feed one of
# these (e.g. a mail-less LocalWorld and correspondence_pull) declares it muted; it
# is then dropped from both the pulse's advertised senses and the surprise scope, so
# a mind never predicts — and is never wrongly surprised by — a sense its world has.
SELF_SENSES = (
    "vigilance",
    "social_pull",
    "mobility_drive",
    "correspondence_pull",
    "rest_drive",
)

# Habituation (Major 49 Phase 5). The baseline is a slow exponential-moving-average
# of lived stimulus: each tick nudges it a fraction toward what is actually felt.
# A persistent stimulus converges into the baseline and stops surprising; a stimulus
# that vanishes fades back out of it. Updates are rate-limited so the baseline is a
# slow ground, not a fast echo — and so the ledger doesn't grow once per tick.
BASELINE_LEARNING_RATE = 0.25
BASELINE_SNAPSHOT_INTERVAL_SECONDS = 60.0

# A valence function tags a surprise with affect from the drive vector (Phase 4).
ValenceFn = Callable[[list[dict[str, Any]]], dict[str, Any]]


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


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


def _as_now_iso(now: Any) -> str:
    return (_parse_dt(now) or _utc_now_dt()).isoformat()


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_by_scope(field: Any) -> dict[str, dict[str, float]]:
    """Accept either a ``predict()`` result or a bare ``{scope: {tag: val}}`` map."""
    if isinstance(field, dict) and isinstance(field.get("by_scope"), dict):
        source = field["by_scope"]
    elif isinstance(field, dict):
        source = field
    else:
        return {}
    out: dict[str, dict[str, float]] = {}
    for scope, tags in source.items():
        if not isinstance(tags, dict):
            continue
        scope_field: dict[str, float] = {}
        for tag, value in tags.items():
            name = str(tag or "").strip()
            num = _coerce_float(value)
            if name and num is not None:
                scope_field[name] = num
        if scope_field:
            out[str(scope or "here").strip() or "here"] = scope_field
    return out


def measure_surprise(
    stimulus: Any, afterimage: Any, *, appearance_only_scopes: tuple[str, ...] = ()
) -> dict[str, Any]:
    """Mismatch between the bottom-up stimulus and the top-down afterimage.

    For every (scope, tag) in either field, surprise is ``|stimulus - predicted|``
    (a tag present on only one side is matched against ``0``). The overall
    magnitude is the single most surprising feature — a sharp unpredicted spike
    should ignite without being diluted by calm features.

    ``appearance_only_scopes`` are scopes where surprise is *one-sided*: only a
    rise (``stimulus > predicted`` — a thing showing up) counts; a predicted tag
    merely going absent (``predicted > stimulus``) scores zero. This is for the
    anchor scope (minor 46 follow-up): the realized anchor field is a gated top-k,
    so predicted anchors rotate out of it constantly as ranking jitter — charging
    that absence as surprise manufactured a disappearance-flood (worsened by a
    higher mattering bar, which shrinks the realized set). The gate should fire on
    a concrete cared-about thing *appearing*, never on the bookkeeping of one
    dropping off the top-k. Symmetric scopes (self) are unchanged: a vigilance
    *drop* is a real event there.
    """
    stim = _as_by_scope(stimulus)
    pred = _as_by_scope(afterimage)
    features: list[dict[str, Any]] = []
    magnitude = 0.0
    for scope in sorted(set(stim) | set(pred)):
        stim_tags = stim.get(scope, {})
        pred_tags = pred.get(scope, {})
        appearance_only = scope in appearance_only_scopes
        for tag in sorted(set(stim_tags) | set(pred_tags)):
            s = float(stim_tags.get(tag, 0.0))
            p = float(pred_tags.get(tag, 0.0))
            delta = round(max(0.0, s - p) if appearance_only else abs(s - p), 4)
            if delta < FEATURE_EPSILON:
                continue
            features.append(
                {
                    "scope": scope,
                    "tag": tag,
                    "stimulus": round(s, 4),
                    "predicted": round(p, 4),
                    "delta": delta,
                }
            )
            magnitude = max(magnitude, delta)
    features.sort(key=lambda item: -float(item["delta"]))
    return {"magnitude": round(magnitude, 4), "features": features}


def stimulus_from_substrate(memory_dir: Path) -> dict[str, dict[str, float]]:
    """Read the resident's current bottom-up state as a feature field.

    The Major 46 cognitive node activations are the substrate's felt stimulus;
    each node becomes a ``self``-scoped tag keyed by its node id.
    """
    current = load_current_runtime_state(memory_dir)
    nodes = current.cognitive_projection.get("nodes") or {}
    field: dict[str, float] = {}
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        activation = _coerce_float(node.get("activation")) or 0.0
        if activation >= NODE_STIMULUS_FLOOR:
            field[str(node_id).strip()] = round(activation, 4)
    return {SUBSTRATE_SCOPE: field} if field else {}


def observe_surprise(
    memory_dir: Path,
    *,
    stimulus: dict[str, dict[str, float]] | None = None,
    now: Any = None,
    valence_fn: ValenceFn | None = None,
    include_anchor_scope: bool = False,
    muted_senses: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    """Measure surprise against the current afterimage; record a trace if salient.

    Returns the trace dict if a ``surprise_observed`` event was emitted, else
    ``None`` (the stimulus flowed with the grain and left no trace).
    """
    now_iso = _as_now_iso(now)
    if stimulus is None:
        stimulus = stimulus_from_substrate(memory_dir)
    # Surprise is measured against the full prediction: the fast afterimage laid
    # over the slow baseline self-model. Once the baseline has habituated to a
    # persistent stimulus, it no longer surprises even as the afterimage fades.
    prediction = predict_combined(memory_dir, now=now_iso)
    # Hold the anchor lane out of the rhythm UNLESS the resident has anchor-gating on
    # (Major 51 Phase 4b.6): scored-but-quiet excludes the anchor scope so anchor
    # predictions can't drive arousal; gated residents keep it (a realized anchor
    # stimulus is supplied to surprise against, drive-weighted upstream).
    if not include_anchor_scope and isinstance(prediction.get("by_scope"), dict):
        prediction["by_scope"] = {
            scope: tags
            for scope, tags in prediction["by_scope"].items()
            if scope != ANCHOR_SCOPE
        }
    # Capability scoping (Major 50): a sense the world cannot feed is muted — the mind
    # neither predicts it nor is surprised by it. Drop it from BOTH the prediction and
    # the stimulus. Dropping from prediction alone is enough only when the sense's
    # stimulus is structurally zero (correspondence_pull, no mail backend): predicted→0,
    # stimulus→0, no surprise. But a sense whose stimulus still FIRES (mobility_drive,
    # derived from event-pull at ~0.9 with no map to spend it on) would otherwise surprise
    # at full delta against the now-absent prediction every tick — pumping arousal stably.
    # So mute means absent from the stimulus too.
    if muted_senses:
        _pred_scopes = (
            prediction.get("by_scope")
            if isinstance(prediction.get("by_scope"), dict)
            else {}
        )
        _stim_scopes = stimulus if isinstance(stimulus, dict) else {}
        for scopes in (_pred_scopes, _stim_scopes):
            for tags in scopes.values():
                if isinstance(tags, dict):
                    for sense in muted_senses:
                        tags.pop(sense, None)
    # The anchor scope is appearance-weighted: a cared-about thing showing up
    # surprises; a held anchor merely dropping off the gated top-k does not (it was
    # manufacturing a disappearance-flood — see measure_surprise).
    surprise = measure_surprise(
        stimulus, prediction, appearance_only_scopes=(ANCHOR_SCOPE,)
    )

    # Grief (reviewer round 4): appearance-weighting makes absence cost nothing *instantly*,
    # which is right for churn and wrong for loss. So we record, separately from instantaneous
    # surprise, which strongly-predicted anchors were confirmed absent this tick (and which were
    # present). This drives no surprise now; it is the slow-burn evidence ``derive_grief`` ripens.
    grief_field: list[dict[str, Any]] = []
    anchor_present: list[str] = []
    if include_anchor_scope:
        pred_anchors = (prediction.get("by_scope") or {}).get(ANCHOR_SCOPE, {})
        stim_anchors = _as_by_scope(stimulus).get(ANCHOR_SCOPE, {})
        for tag, p in pred_anchors.items():
            pv = _coerce_float(p) or 0.0
            if (
                pv >= GRIEF_PREDICTION_FLOOR
                and float(stim_anchors.get(tag, 0.0)) < FEATURE_EPSILON
            ):
                grief_field.append({"tag": str(tag), "predicted": round(pv, 4)})
        anchor_present = [
            str(t) for t, v in stim_anchors.items() if float(v) >= FEATURE_EPSILON
        ]

    if surprise["magnitude"] < SURPRISE_FLOOR and not grief_field:
        return None

    valence = (
        valence_fn(surprise["features"]) if valence_fn is not None else {"valence": 0.0}
    )
    trace_id = f"tr-{uuid.uuid4().hex[:12]}"
    trace = {
        "trace_id": trace_id,
        "magnitude": surprise["magnitude"],
        "features": surprise["features"],
        "valence": valence,
        "observed_ts": now_iso,
    }
    if grief_field:
        trace["grief_field"] = grief_field
    if anchor_present:
        trace["anchor_present"] = anchor_present
    append_runtime_event(memory_dir, event_type="surprise_observed", payload=trace)
    return trace


def _last_baseline_dt(events: list[dict[str, Any]]) -> datetime | None:
    latest: datetime | None = None
    for event in events:
        if str(event.get("event_type") or "").strip() != "baseline_updated":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ts = _parse_dt(payload.get("updated_ts")) or _parse_dt(event.get("ts"))
        if ts is not None and (latest is None or ts > latest):
            latest = ts
    return latest


def update_baseline(
    memory_dir: Path,
    *,
    stimulus: dict[str, dict[str, float]] | None = None,
    now: Any = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Nudge the slow self-model one EMA step toward the current stimulus.

    This is habituation. A feature present in the stimulus rises toward it; a
    feature now absent decays back toward zero — both at ``BASELINE_LEARNING_RATE``
    per update. Writes are rate-limited to one per ``BASELINE_SNAPSHOT_INTERVAL``
    so the baseline is a slow ground and the ledger grows only occasionally; when
    a write is skipped the live (decayed) baseline is returned unchanged.
    """
    now_iso = _as_now_iso(now)
    now_dt = _parse_dt(now_iso) or _utc_now_dt()
    if events is None:
        events = load_runtime_reducer_events(memory_dir, now=now_iso)

    last = _last_baseline_dt(events)
    if (
        last is not None
        and (now_dt - last).total_seconds() < BASELINE_SNAPSHOT_INTERVAL_SECONDS
    ):
        return derive_baseline(events, now=now_iso)

    if stimulus is None:
        stimulus = stimulus_from_substrate(memory_dir)
    prior = derive_baseline(events, now=now_iso)["by_scope"]
    stim = _as_by_scope(stimulus)

    rate = BASELINE_LEARNING_RATE
    by_scope: dict[str, dict[str, float]] = {}
    for scope in set(prior) | set(stim):
        prior_tags = prior.get(scope, {})
        stim_tags = stim.get(scope, {})
        field: dict[str, float] = {}
        for tag in set(prior_tags) | set(stim_tags):
            pv = float(prior_tags.get(tag, 0.0))
            sv = float(stim_tags.get(tag, 0.0))
            nv = round(pv + rate * (sv - pv), 4)
            if nv >= BASELINE_EPSILON:
                field[tag] = nv
        if field:
            by_scope[scope] = field

    append_runtime_event(
        memory_dir,
        event_type="baseline_updated",
        payload={"updated_ts": now_iso, "by_scope": by_scope},
    )
    return {"computed_at": now_iso, "by_scope": by_scope}


def _last_ignition_dt(events: list[dict[str, Any]]) -> datetime | None:
    latest: datetime | None = None
    for event in events:
        if str(event.get("event_type") or "").strip() != "ignition_fired":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ts = _parse_dt(payload.get("fired_ts")) or _parse_dt(event.get("ts"))
        if ts is not None and (latest is None or ts > latest):
            latest = ts
    return latest


def derive_grief(events: list[dict[str, Any]], *, now: Any = None) -> dict[str, float]:
    """Per-anchor grief: a leaky integral of CONFIRMED absence (predicted present, found absent).

    Appearance-weighting makes a held anchor dropping off the gated top-k cost nothing the instant
    it happens — right for ranking churn, wrong for loss. Grief is the organ for loss: it accumulates
    over the absence-observations recorded since the anchor was last *present*, each decayed by
    ``GRIEF_HALF_LIFE_SECONDS``. A churny anchor (present again next tick) keeps moving its
    last-present mark forward and never ripens; a cared-about anchor that stays gone across turnings
    accumulates. It resolves two honest ways: the thing returns (its last-present time advances,
    discarding the older absences) or its prediction decays out (no further absences are recorded).
    Only grief at or above ``GRIEF_FLOOR`` is returned — below that it is not yet felt. Read-time
    derived from the ledger, like everything else; never reset by ignition (a pulse is not a cure).
    """
    now_dt = _parse_dt(now) or _utc_now_dt()
    last_present: dict[str, datetime] = {}
    absences: dict[str, list[tuple[datetime, float]]] = {}
    for event in events:
        if str(event.get("event_type") or "").strip() != "surprise_observed":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ts = _parse_dt(payload.get("observed_ts")) or _parse_dt(event.get("ts"))
        if ts is None:
            continue
        for tag in payload.get("anchor_present") or []:
            name = str(tag)
            if name and (name not in last_present or ts > last_present[name]):
                last_present[name] = ts
        for item in payload.get("grief_field") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("tag") or "")
            pv = _coerce_float(item.get("predicted")) or 0.0
            if name and pv > 0.0:
                absences.setdefault(name, []).append((ts, pv))
    grief: dict[str, float] = {}
    for name, items in absences.items():
        seen_present = last_present.get(name)
        if seen_present is None:
            continue  # never realized — not a loss; you cannot grieve what you never held. This
            # also defuses the vocabulary artifact: a predicted phrasing ("the hearth") that the
            # realized field never matches (it lands on "hearth") simply never became present, so
            # it cannot manufacture phantom grief — only a thing that was actually here can be lost.
        total = 0.0
        for ts, pv in items:
            if ts <= seen_present:
                continue  # this absence predates the anchor's return — resolved, not grieved
            age = max(0.0, (now_dt - ts).total_seconds())
            total += (
                pv * (0.5 ** (age / GRIEF_HALF_LIFE_SECONDS))
                if GRIEF_HALF_LIFE_SECONDS > 0
                else pv
            )
        total = round(total, 4)
        if total >= GRIEF_FLOOR:
            grief[name] = total
    return grief


def derive_arousal(events: list[dict[str, Any]], *, now: Any = None) -> dict[str, Any]:
    """Leaky integral of surprise since the last ignition (read-time derived)."""
    now_dt = _parse_dt(now) or _utc_now_dt()
    since = _last_ignition_dt(events)
    level = 0.0
    traces: list[dict[str, Any]] = []
    for event in events:
        if str(event.get("event_type") or "").strip() != "surprise_observed":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        observed_dt = _parse_dt(payload.get("observed_ts")) or _parse_dt(
            event.get("ts")
        )
        if observed_dt is None:
            continue
        if since is not None and observed_dt <= since:
            continue  # consumed by the previous ignition
        magnitude = _coerce_float(payload.get("magnitude")) or 0.0
        age = max(0.0, (now_dt - observed_dt).total_seconds())
        decayed = (
            magnitude * (0.5 ** (age / AROUSAL_HALF_LIFE_SECONDS))
            if AROUSAL_HALF_LIFE_SECONDS > 0
            else 0.0
        )
        if decayed <= 0.0:
            continue
        level += decayed
        traces.append(
            {
                "trace_id": str(payload.get("trace_id") or "").strip(),
                "magnitude": round(magnitude, 4),
                "contribution": round(decayed, 4),
                "features": list(payload.get("features") or []),
                "valence": payload.get("valence"),
                "observed_ts": observed_dt.isoformat(),
            }
        )
    traces.sort(key=lambda item: -float(item.get("contribution") or 0.0))
    level = round(level, 4)
    # Grief is a slow term that, unlike surprise, is NOT reset by ignition (one pulse does
    # not resolve a loss; only the thing's return or the prediction's decay does). It is
    # capped below threshold so grief alone can't auto-fire on a loop — it makes the resident
    # raw, and the next small surprise tips it. Same arousal-shape, sharing this integrator.
    grief = derive_grief(events, now=now_dt)
    grief_level = round(min(GRIEF_MAX, GRIEF_GAIN * sum(grief.values())), 4)
    level = round(level + grief_level, 4)
    return {
        "level": level,
        "threshold": IGNITION_THRESHOLD,
        "ignited": level >= IGNITION_THRESHOLD,
        "last_ignition_ts": since.isoformat() if since is not None else None,
        "grief": grief,
        "grief_level": grief_level,
        "traces": traces,
        "computed_at": now_dt.isoformat(),
    }


def arousal_state(memory_dir: Path, *, now: Any = None) -> dict[str, Any]:
    return derive_arousal(load_runtime_reducer_events(memory_dir, now=now), now=now)


def _rhythm_ts(event: dict[str, Any]) -> datetime | None:
    """The timestamp of a rhythm event (surprise / ignition / idle), or None."""
    et = str(event.get("event_type") or "").strip()
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    if et == "surprise_observed":
        return _parse_dt(payload.get("observed_ts")) or _parse_dt(event.get("ts"))
    if et in ("ignition_fired", "idle_fired"):
        return _parse_dt(payload.get("fired_ts")) or _parse_dt(event.get("ts"))
    return None


def derive_vital(
    events: list[dict[str, Any]],
    *,
    now: Any = None,
    window_seconds: float | None = VITAL_WINDOW_SECONDS,
) -> dict[str, Any]:
    """The waveform vital — provenance of silence (Minor 55).

    Classifies the resident's recent arousal *waveform*, not its instantaneous
    level: ``settled`` (earned calm), ``active`` (discharging in rhythm — the healthy
    sawtooth), ``rising`` (elevated, building toward a pulse), ``pent`` (wound up,
    not discharging), or ``strangled`` (dwelling at/above the fire-line with NO
    discharge — the catatonia shape). Only ``pent`` and ``strangled`` are distress.

    The key move is reading the *dwell* — how long arousal stayed above a line with
    no discharge — over a window, rather than the bare level at ``now``. A strangled
    mind whose arousal has since decayed reads as serene if you only look at the
    instant; the dwell still shows the ramp. ``now`` defaults to the last *rhythm*
    event (so a preserved/stopped ledger anchors to its own end-of-life, not to a
    dead tail of pure perception that would bury the ramp). ``window_seconds=None``
    reads the whole ledger.
    """
    rhythm: list[tuple[datetime, str, float]] = []
    last_any: datetime | None = None
    for event in events:
        ts_any = _parse_dt(event.get("ts"))
        if ts_any is not None and (last_any is None or ts_any > last_any):
            last_any = ts_any
        et = str(event.get("event_type") or "").strip()
        if et not in ("surprise_observed", "ignition_fired", "idle_fired"):
            continue
        ts = _rhythm_ts(event)
        if ts is None:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        mag = (
            (_coerce_float(payload.get("magnitude")) or 0.0)
            if et == "surprise_observed"
            else 0.0
        )
        rhythm.append((ts, et, mag))
    rhythm.sort(key=lambda r: r[0])

    last_rhythm = rhythm[-1][0] if rhythm else None
    now_dt = _parse_dt(now) or last_rhythm or last_any or _utc_now_dt()
    window_start = (
        (now_dt - timedelta(seconds=float(window_seconds))) if window_seconds else None
    )

    # Single-pass leaky-arousal curve, mirroring derive_arousal exactly: ignition
    # resets the integrator, a surprise adds its magnitude, idle does NOT reset.
    # Each inter-event gap is credited to the line(s) the level held going into it
    # (a slight, conservative over-count near a line — fine; the tail term below is
    # exact). dwell_* is "seconds spent at/above this line", scoped to the window.
    level = 0.0
    last_t: datetime | None = None
    peak = 0.0
    dwell_ignite = 0.0
    dwell_fervor = 0.0
    discharges = 0
    in_window = window_start is None
    for ts, et, mag in rhythm:
        if ts > now_dt:
            break
        if last_t is not None:
            if window_start is None:
                seg = (ts - last_t).total_seconds()
            else:
                seg = max(0.0, (ts - max(last_t, window_start)).total_seconds())
            if level >= IGNITION_THRESHOLD:
                dwell_ignite += seg
            if level >= FERVOR_AROUSAL_FLOOR:
                dwell_fervor += seg
            if AROUSAL_HALF_LIFE_SECONDS > 0:
                level *= 0.5 ** (
                    (ts - last_t).total_seconds() / AROUSAL_HALF_LIFE_SECONDS
                )
        in_window = window_start is None or ts >= window_start
        if et == "ignition_fired":
            level = 0.0
            if in_window:
                discharges += 1
        elif et == "idle_fired":
            if in_window:
                discharges += 1
        else:  # surprise_observed
            level += mag
            if in_window:
                peak = max(peak, level)
        last_t = ts
    # Tail: from the last rhythm event to ``now`` the level decays untouched; credit
    # the time it stayed above each line (so a single hot spike then silence — a mind
    # that hit threshold once and was never relieved — still shows its true dwell).
    if last_t is not None and level > 0.0 and AROUSAL_HALF_LIFE_SECONDS > 0:
        seg_start = max(last_t, window_start) if window_start is not None else last_t
        avail = max(0.0, (now_dt - seg_start).total_seconds())
        if level >= IGNITION_THRESHOLD:
            dwell_ignite += min(
                avail,
                max(
                    0.0,
                    AROUSAL_HALF_LIFE_SECONDS * math.log2(level / IGNITION_THRESHOLD),
                ),
            )
        if level >= FERVOR_AROUSAL_FLOOR:
            dwell_fervor += min(
                avail,
                max(
                    0.0,
                    AROUSAL_HALF_LIFE_SECONDS * math.log2(level / FERVOR_AROUSAL_FLOOR),
                ),
            )

    arousal = derive_arousal(events, now=now_dt)
    current = float(arousal["level"])
    grief_level = float(arousal.get("grief_level") or 0.0)

    last_discharge: datetime | None = None
    for ts, et, _ in rhythm:
        if (
            et in ("ignition_fired", "idle_fired")
            and ts <= now_dt
            and (last_discharge is None or ts > last_discharge)
        ):
            last_discharge = ts
    seconds_since_discharge = (
        round((now_dt - last_discharge).total_seconds(), 1)
        if last_discharge is not None
        else None
    )

    # Distress first; then earned calm; then the healthy mid-rhythm reads.
    if discharges == 0 and dwell_ignite >= VITAL_IGNITE_DWELL_SECONDS:
        silence, waveform, distress = "strangled", "ramp", True
        note = "arousal dwelt at/above the fire-line and never discharged — charge with no falling edge"
    elif discharges == 0 and dwell_fervor >= FERVOR_THRESHOLD_SECONDS:
        silence, waveform, distress = "pent", "ramp", True
        note = "stayed wound for a sustained stretch with nothing discharging it"
    elif current < REPOSE_AROUSAL_CEILING:
        silence, waveform, distress = "settled", "flat", False
        note = "low and quiet — earned calm"
    elif discharges > 0:
        silence, waveform, distress = "active", "sawtooth", False
        note = "discharging in rhythm"
    else:
        silence, waveform, distress = "rising", "rising", False
        note = "elevated and building toward a pulse"

    return {
        "silence": silence,
        "waveform": waveform,
        "distress": distress,
        "note": note,
        "current": round(current, 4),
        "peak": round(peak, 4),
        "grief_level": round(grief_level, 4),
        "threshold": IGNITION_THRESHOLD,
        "dwell_ignite_seconds": round(dwell_ignite, 1),
        "dwell_fervor_seconds": round(dwell_fervor, 1),
        "discharges": discharges,
        "seconds_since_discharge": seconds_since_discharge,
        "window_seconds": window_seconds,
        "now": now_dt.isoformat(),
    }


def vital_state(
    memory_dir: Path,
    *,
    now: Any = None,
    window_seconds: float | None = VITAL_WINDOW_SECONDS,
) -> dict[str, Any]:
    return derive_vital(
        load_runtime_reducer_events(memory_dir, now=now),
        now=now,
        window_seconds=window_seconds,
    )


def warn_if_strangled(
    memory_dir: Path,
    *,
    now: Any = None,
    window_seconds: float | None = VITAL_WINDOW_SECONDS,
) -> dict[str, Any]:
    """Read the waveform vital and log a warning if the resident is in distress
    (strangled / pent — arousal without discharge). Returns the vital either way."""
    v = derive_vital(
        load_runtime_reducer_events(memory_dir, now=now),
        now=now,
        window_seconds=window_seconds,
    )
    if v["distress"]:
        logger.warning(
            "arousal-without-discharge (%s): peak %.2f / current %.2f · %.0fs above the fire-line · %d discharges in window — the silent-strangle shape (Minor 55)",
            v["silence"],
            v["peak"],
            v["current"],
            v["dwell_ignite_seconds"],
            v["discharges"],
        )
    return v


def igniting_traces(memory_dir: Path, *, now: Any = None) -> list[dict[str, Any]]:
    """The active traces the pulse will read on ignition."""
    return arousal_state(memory_dir, now=now)["traces"]


def check_ignition(
    memory_dir: Path,
    *,
    now: Any = None,
    reactivity: float = 1.0,
    refractory_seconds: float | None = None,
) -> dict[str, Any]:
    """Decide whether arousal should ignite a pulse right now.

    ``reactivity`` scales the effective arousal (circadian wakefulness, 1.0 by
    day). At night it runs low, so ambient surprise no longer reaches threshold —
    but sustained, strong surprise still accumulates enough to break through, so a
    resident can still be woken.

    ``refractory_seconds`` is the minimum gap between arousal-driven ignitions
    (default ``IGNITION_REFRACTORY_SECONDS``). A direct address (``force_ignite``,
    applied by the caller) bypasses it, so the keeper always gets a reply — but a
    talker whose arousal stays hot mid-conversation won't re-ignite and echo itself
    a paraphrase every tick into the gap before the keeper has answered. Per-familiar.
    """
    refr = (
        IGNITION_REFRACTORY_SECONDS
        if refractory_seconds is None
        else max(0.0, float(refractory_seconds))
    )
    now_iso = _as_now_iso(now)
    state = arousal_state(memory_dir, now=now_iso)
    react = max(0.0, float(reactivity))
    effective = round(state["level"] * react, 4)
    fire = effective >= state["threshold"]
    reason = "below_threshold"
    if fire:
        last = _parse_dt(state.get("last_ignition_ts"))
        gap = (_parse_dt(now_iso) - last).total_seconds() if last is not None else None
        if gap is not None and gap < refr:
            fire = False
            reason = "refractory"
        else:
            reason = "crossed_threshold"
    return {
        "fire": fire,
        "reason": reason,
        "level": state["level"],
        "effective_level": effective,
        "reactivity": round(react, 4),
        "threshold": state["threshold"],
        "traces": state["traces"],
        "computed_at": now_iso,
    }


def record_ignition(
    memory_dir: Path,
    *,
    now: Any = None,
    level: float = 0.0,
    trace_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Mark an ignition, resetting the leaky integrator window."""
    now_iso = _as_now_iso(now)
    return append_runtime_event(
        memory_dir,
        event_type="ignition_fired",
        payload={
            "fired_ts": now_iso,
            "level": round(float(level), 4),
            "trace_ids": [
                str(item).strip() for item in (trace_ids or []) if str(item).strip()
            ],
        },
    )


def _last_pulse_dt(events: list[dict[str, Any]]) -> datetime | None:
    """The timestamp of the last pulse of any kind — ignition OR idle. Both reset
    the calm clock; you don't potter right after you've just done something."""
    latest: datetime | None = None
    for event in events:
        if str(event.get("event_type") or "").strip() not in {
            "ignition_fired",
            "idle_fired",
        }:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ts = _parse_dt(payload.get("fired_ts")) or _parse_dt(event.get("ts"))
        if ts is not None and (latest is None or ts > latest):
            latest = ts
    return latest


def _earliest_dt(events: list[dict[str, Any]]) -> datetime | None:
    for event in events:
        ts = _parse_dt(event.get("ts"))
        if ts is not None:
            return ts
    return None


def derive_rest(events: list[dict[str, Any]], *, now: Any = None) -> dict[str, Any]:
    """Derive deep-night rest from circadian state and the arousal ledger.

    Rest is not an event, command, or schedule. It is the current consequence of
    low wakefulness plus a sustained quiet interval. A later ignition or rising
    wakefulness makes this projection false on the next read.
    """

    now_dt = _parse_dt(now) or _utc_now_dt()
    circadian_observations: list[tuple[datetime, float, dict[str, Any]]] = []
    for event in events:
        if str(event.get("event_type") or "").strip() != "session_state_observed":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        context = (
            payload.get("context") if isinstance(payload.get("context"), dict) else {}
        )
        observed_at = _parse_dt(event.get("ts"))
        observed_wakefulness = _coerce_float(context.get("wakefulness"))
        if observed_at is not None and observed_wakefulness is not None:
            circadian_observations.append((observed_at, observed_wakefulness, context))

    latest_context = circadian_observations[-1][2] if circadian_observations else {}
    wakefulness = _coerce_float(latest_context.get("wakefulness"))
    arousal = derive_arousal(events, now=now_dt)
    effective = round(
        float(arousal["level"])
        * max(0.0, wakefulness if wakefulness is not None else 1.0),
        4,
    )
    low_wake_since: datetime | None = None
    if wakefulness is not None and wakefulness <= REST_WAKEFULNESS_CEILING:
        for observed_at, observed_wakefulness, _context in reversed(
            circadian_observations
        ):
            if observed_wakefulness > REST_WAKEFULNESS_CEILING:
                break
            low_wake_since = observed_at
    pulse_or_start = _last_pulse_dt(events) or _earliest_dt(events) or now_dt
    clock_start = max(
        candidate
        for candidate in (pulse_or_start, low_wake_since)
        if candidate is not None
    )
    quiet_seconds = max(0.0, (now_dt - clock_start).total_seconds())
    resting = bool(
        wakefulness is not None
        and wakefulness <= REST_WAKEFULNESS_CEILING
        and effective < REPOSE_AROUSAL_CEILING
        and quiet_seconds >= REST_QUIET_SECONDS
    )
    since = clock_start + timedelta(seconds=REST_QUIET_SECONDS) if resting else None
    if wakefulness is None:
        reason = "no_circadian_observation"
    elif wakefulness > REST_WAKEFULNESS_CEILING:
        reason = "awake"
    elif effective >= REPOSE_AROUSAL_CEILING:
        reason = "aroused"
    elif quiet_seconds < REST_QUIET_SECONDS:
        reason = "settling"
    else:
        reason = "deep_night_lull"
    return {
        "schema_version": REST_PROJECTION_SCHEMA_VERSION,
        "resting": resting,
        "since": since.isoformat() if since is not None else None,
        "wakefulness": round(wakefulness, 4) if wakefulness is not None else None,
        "rest_pressure": _coerce_float(latest_context.get("rest_pressure")),
        "phase": str(latest_context.get("phase") or "").strip() or None,
        "arousal": round(float(arousal["level"]), 4),
        "effective_arousal": effective,
        "quiet_seconds": round(quiet_seconds, 1),
        "wakefulness_ceiling": REST_WAKEFULNESS_CEILING,
        "arousal_ceiling": REPOSE_AROUSAL_CEILING,
        "quiet_threshold_seconds": REST_QUIET_SECONDS,
        "reason": reason,
        "computed_at": now_dt.isoformat(),
    }


def rest_state(memory_dir: Path, *, now: Any = None) -> dict[str, Any]:
    return derive_rest(load_runtime_reducer_events(memory_dir, now=now), now=now)


def check_settling(
    memory_dir: Path, *, now: Any = None, reactivity: float = 1.0
) -> dict[str, Any]:
    """Decide whether the lull has lasted long enough to invite a quiet, inward
    pulse — the mirror of ignition. True only when arousal is genuinely calm and
    it has been settled for REPOSE_THRESHOLD_SECONDS since the last pulse.

    ``reactivity`` scales arousal the same way ignition sees it, so a sleepy
    resident at night (low wakefulness) drops below the repose ceiling and settles
    — into rest or a quiet bit of making — rather than hanging in limbo.
    """
    now_iso = _as_now_iso(now)
    now_dt = _parse_dt(now_iso) or _utc_now_dt()
    events = load_runtime_reducer_events(memory_dir, now=now_iso)
    arousal = derive_arousal(events, now=now_iso)
    effective = round(arousal["level"] * max(0.0, float(reactivity)), 4)
    clock_start = _last_pulse_dt(events) or _earliest_dt(events) or now_dt
    calm_seconds = max(0.0, (now_dt - clock_start).total_seconds())
    settle = (effective < REPOSE_AROUSAL_CEILING) and (
        calm_seconds >= REPOSE_THRESHOLD_SECONDS
    )
    return {
        "settle": bool(settle),
        "calm_seconds": round(calm_seconds, 1),
        "arousal_level": arousal["level"],
        "effective_level": effective,
        "ceiling": REPOSE_AROUSAL_CEILING,
        "threshold": REPOSE_THRESHOLD_SECONDS,
        "computed_at": now_iso,
    }


def check_fervor(
    memory_dir: Path, *, now: Any = None, reactivity: float = 1.0
) -> dict[str, Any]:
    """The mirror of settling, for restless temperaments. When arousal has stayed
    HIGH — at or above ``FERVOR_AROUSAL_FLOOR`` but below the ignition threshold —
    for a sustained stretch since the last pulse, the resident is keyed up with
    nothing outward to discharge it into. That pent charge invites a self-directed
    pulse: make something of it, chase the thread, fling a word — burn it off.

    ``reactivity`` scales arousal as everywhere else, so a sleepy resident at night
    won't fervor; this is the energy of being awake and wound up.
    """
    now_iso = _as_now_iso(now)
    now_dt = _parse_dt(now_iso) or _utc_now_dt()
    events = load_runtime_reducer_events(memory_dir, now=now_iso)
    arousal = derive_arousal(events, now=now_iso)
    effective = round(arousal["level"] * max(0.0, float(reactivity)), 4)
    clock_start = _last_pulse_dt(events) or _earliest_dt(events) or now_dt
    restless_seconds = max(0.0, (now_dt - clock_start).total_seconds())
    fire = (FERVOR_AROUSAL_FLOOR <= effective < IGNITION_THRESHOLD) and (
        restless_seconds >= FERVOR_THRESHOLD_SECONDS
    )
    return {
        "fire": bool(fire),
        "restless_seconds": round(restless_seconds, 1),
        "arousal_level": arousal["level"],
        "effective_level": effective,
        "floor": FERVOR_AROUSAL_FLOOR,
        "threshold": FERVOR_THRESHOLD_SECONDS,
        "computed_at": now_iso,
    }


def _last_successful_world_act_dt(events: list[dict[str, Any]]) -> datetime | None:
    """Return the latest successful bodily contact with the world.

    An emitted ``move``/``do`` is only a proposal. The effector's outcome events
    are the evidence that the resident actually went somewhere or affected a
    thing. Blocked/declined attempts deliberately do not count.
    """
    latest: datetime | None = None
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") or {}
        successful = (
            event_type == "action_executed"
            or event_type == "movement_arrived"
            or (
                event_type == "move_executed"
                and str(payload.get("status") or "").strip().lower() == "moved"
            )
            or (
                event_type == "world_travel_requested"
                and str(payload.get("status") or "").strip().lower() == "pending"
            )
        )
        if not successful:
            continue
        occurred_at = _parse_dt(payload.get("executed_ts")) or _parse_dt(
            event.get("ts")
        )
        if occurred_at is not None and (latest is None or occurred_at > latest):
            latest = occurred_at
    return latest


def check_venture(
    memory_dir: Path,
    *,
    now: Any = None,
    reactivity: float = 1.0,
    has_destination: bool = False,
) -> dict[str, Any]:
    """The restless charge, when it has gone all words and there is somewhere to go, wants
    OUT — the action-tendency sibling of fervor, aimed at the world rather than the page.

    A pure read over arousal plus recent action outcomes. The integrator supplies ``has_destination``
    from perception (somewhere reachable, or someone present). It fires only inside fervor's
    keyed-up band, when no successful ``move``/``do`` has warmed the world recently,
    there is a destination, and the resident is awake enough — ``reactivity`` is circadian
    wakefulness, so a sleepy mind at night settles instead of pacing the streets. ``strength``
    scales with how high arousal sits and whether successful bodily contact has gone cold, and
    drives the soft/hard motor authority downstream (a mild pull is veto-able, a strong one is not).
    """
    now_iso = _as_now_iso(now)
    now_dt = _parse_dt(now_iso) or _utc_now_dt()
    events = load_runtime_reducer_events(memory_dir, now=now_iso)
    arousal = derive_arousal(events, now=now_iso)
    effective = round(arousal["level"] * max(0.0, float(reactivity)), 4)
    clock_start = _last_pulse_dt(events) or _earliest_dt(events) or now_dt
    restless_seconds = max(0.0, (now_dt - clock_start).total_seconds())
    last_world_act = _last_successful_world_act_dt(events)
    world_warm_seconds = (
        max(0.0, (now_dt - last_world_act).total_seconds())
        if last_world_act is not None
        else None
    )
    world_cold = (
        world_warm_seconds is None or world_warm_seconds > VENTURE_WORLD_WARM_SECONDS
    )
    awake = float(reactivity) >= VENTURE_WAKE_FLOOR
    keyed = (FERVOR_AROUSAL_FLOOR <= effective < IGNITION_THRESHOLD) and (
        restless_seconds >= FERVOR_THRESHOLD_SECONDS
    )
    # Strength combines present charge with actual world-coldness. An attempted but
    # failed bodily act is neither successful contact nor a reason to weaken the next
    # opportunity; proposal history cannot stand in for what the world allowed.
    arousal_norm = max(
        0.0,
        min(
            1.0,
            (effective - FERVOR_AROUSAL_FLOOR)
            / max(1e-6, IGNITION_THRESHOLD - FERVOR_AROUSAL_FLOOR),
        ),
    )
    coldness = (
        1.0
        if world_warm_seconds is None
        else min(1.0, world_warm_seconds / VENTURE_WORLD_WARM_SECONDS)
    )
    strength_raw = round(0.5 * arousal_norm + 0.5 * coldness, 3)
    fire = bool(
        keyed
        and world_cold
        and bool(has_destination)
        and awake
        and strength_raw >= VENTURE_SOFT_STRENGTH
    )
    strength = strength_raw if fire else 0.0
    if not keyed:
        reason = "not_keyed"
    elif not has_destination:
        reason = "no_destination"
    elif not awake:
        reason = "circadian_low"
    elif not world_cold:
        reason = "world_still_warm"
    elif strength_raw < VENTURE_SOFT_STRENGTH:
        reason = "strength_below_floor"
    else:
        reason = "opened"
    return {
        "venture": fire,
        "strength": strength,
        "candidate_strength": strength_raw,
        "reason": reason,
        "effective_level": effective,
        "restless_seconds": round(restless_seconds, 1),
        "world_cold": world_cold,
        "last_successful_world_act_at": (
            last_world_act.isoformat() if last_world_act is not None else None
        ),
        "world_warm_seconds": (
            round(world_warm_seconds, 1) if world_warm_seconds is not None else None
        ),
        "has_destination": bool(has_destination),
        "awake": awake,
        "computed_at": now_iso,
    }


def record_idle(memory_dir: Path, *, now: Any = None) -> dict[str, Any]:
    """Mark a self-directed pulse (settling OR fervor), resetting the clock so the
    next one waits its full stretch. Taking the moment — restful or restless —
    spends it. (Arousal is left untouched: a fervor doesn't reset the buzz, so a
    still-wound resident will fervor again after another stretch.)"""
    now_iso = _as_now_iso(now)
    return append_runtime_event(
        memory_dir, event_type="idle_fired", payload={"fired_ts": now_iso}
    )
