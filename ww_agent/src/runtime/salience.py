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

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.runtime.ledger import append_runtime_event, load_runtime_events, reduce_runtime_events
from src.runtime.substrate import BASELINE_EPSILON, derive_baseline, predict_combined

# Calibration dials (Major 49 risks: ignition threshold + half-lives are the knobs).
SURPRISE_FLOOR = 0.1  # minimum mismatch worth recording as a trace
FEATURE_EPSILON = 0.02  # per-feature mismatch below this is ignored as noise
AROUSAL_HALF_LIFE_SECONDS = 300.0
IGNITION_THRESHOLD = 1.0
IGNITION_REFRACTORY_SECONDS = 30.0

# Settling — the mirror of ignition (Major 50). When arousal has stayed below the
# ceiling for a sustained stretch since the last pulse, the *lull itself* becomes
# a trigger: a quiet, inward, self-directed pulse (reflect, make something, or
# simply rest). Any pulse — ignition or idle — resets the calm clock, so this
# fires only occasionally and a calm resident stays nearly free.
REPOSE_AROUSAL_CEILING = 0.3
REPOSE_THRESHOLD_SECONDS = 300.0

# Fervor — the mirror of settling (Major 50). A restless temperament rarely goes
# calm enough to settle; when arousal stays HIGH (yet below ignition) for a stretch
# with nothing outward to aim it at, that pent charge invites a self-directed pulse
# — make something of it, burn it off — instead of leaving it to buzz with nowhere
# to go. Calm minds make in repose (settling); restless minds make in a fidget.
FERVOR_AROUSAL_FLOOR = 0.45
FERVOR_THRESHOLD_SECONDS = 180.0

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


def measure_surprise(stimulus: Any, afterimage: Any) -> dict[str, Any]:
    """Mismatch between the bottom-up stimulus and the top-down afterimage.

    For every (scope, tag) in either field, surprise is ``|stimulus - predicted|``
    (a tag present on only one side is matched against ``0``). The overall
    magnitude is the single most surprising feature — a sharp unpredicted spike
    should ignite without being diluted by calm features.
    """
    stim = _as_by_scope(stimulus)
    pred = _as_by_scope(afterimage)
    features: list[dict[str, Any]] = []
    magnitude = 0.0
    for scope in sorted(set(stim) | set(pred)):
        stim_tags = stim.get(scope, {})
        pred_tags = pred.get(scope, {})
        for tag in sorted(set(stim_tags) | set(pred_tags)):
            s = float(stim_tags.get(tag, 0.0))
            p = float(pred_tags.get(tag, 0.0))
            delta = round(abs(s - p), 4)
            if delta < FEATURE_EPSILON:
                continue
            features.append({"scope": scope, "tag": tag, "stimulus": round(s, 4), "predicted": round(p, 4), "delta": delta})
            magnitude = max(magnitude, delta)
    features.sort(key=lambda item: -float(item["delta"]))
    return {"magnitude": round(magnitude, 4), "features": features}


def stimulus_from_substrate(memory_dir: Path) -> dict[str, dict[str, float]]:
    """Read the resident's current bottom-up state as a feature field.

    The Major 46 cognitive node activations are the substrate's felt stimulus;
    each node becomes a ``self``-scoped tag keyed by its node id.
    """
    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    nodes = reduced.cognitive_projection.get("nodes") or {}
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
    # Hold the anchor lane out of the rhythm: anchor predictions are scored offline,
    # never surprised against here (no anchor stimulus exists to match them, so they
    # would otherwise read as a constant phantom miss and drive arousal).
    if isinstance(prediction.get("by_scope"), dict):
        prediction["by_scope"] = {scope: tags for scope, tags in prediction["by_scope"].items() if scope != ANCHOR_SCOPE}
    surprise = measure_surprise(stimulus, prediction)
    if surprise["magnitude"] < SURPRISE_FLOOR:
        return None

    valence = valence_fn(surprise["features"]) if valence_fn is not None else {"valence": 0.0}
    trace_id = f"tr-{uuid.uuid4().hex[:12]}"
    trace = {
        "trace_id": trace_id,
        "magnitude": surprise["magnitude"],
        "features": surprise["features"],
        "valence": valence,
        "observed_ts": now_iso,
    }
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
        events = load_runtime_events(memory_dir)

    last = _last_baseline_dt(events)
    if last is not None and (now_dt - last).total_seconds() < BASELINE_SNAPSHOT_INTERVAL_SECONDS:
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

    append_runtime_event(memory_dir, event_type="baseline_updated", payload={"updated_ts": now_iso, "by_scope": by_scope})
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
        observed_dt = _parse_dt(payload.get("observed_ts")) or _parse_dt(event.get("ts"))
        if observed_dt is None:
            continue
        if since is not None and observed_dt <= since:
            continue  # consumed by the previous ignition
        magnitude = _coerce_float(payload.get("magnitude")) or 0.0
        age = max(0.0, (now_dt - observed_dt).total_seconds())
        decayed = magnitude * (0.5 ** (age / AROUSAL_HALF_LIFE_SECONDS)) if AROUSAL_HALF_LIFE_SECONDS > 0 else 0.0
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
    return {
        "level": level,
        "threshold": IGNITION_THRESHOLD,
        "ignited": level >= IGNITION_THRESHOLD,
        "last_ignition_ts": since.isoformat() if since is not None else None,
        "traces": traces,
        "computed_at": now_dt.isoformat(),
    }


def arousal_state(memory_dir: Path, *, now: Any = None) -> dict[str, Any]:
    return derive_arousal(load_runtime_events(memory_dir), now=now)


def igniting_traces(memory_dir: Path, *, now: Any = None) -> list[dict[str, Any]]:
    """The active traces the pulse will read on ignition."""
    return arousal_state(memory_dir, now=now)["traces"]


def check_ignition(memory_dir: Path, *, now: Any = None, reactivity: float = 1.0) -> dict[str, Any]:
    """Decide whether arousal should ignite a pulse right now.

    ``reactivity`` scales the effective arousal (circadian wakefulness, 1.0 by
    day). At night it runs low, so ambient surprise no longer reaches threshold —
    but sustained, strong surprise still accumulates enough to break through, so a
    resident can still be woken.
    """
    now_iso = _as_now_iso(now)
    state = arousal_state(memory_dir, now=now_iso)
    react = max(0.0, float(reactivity))
    effective = round(state["level"] * react, 4)
    fire = effective >= state["threshold"]
    reason = "below_threshold"
    if fire:
        last = _parse_dt(state.get("last_ignition_ts"))
        gap = (_parse_dt(now_iso) - last).total_seconds() if last is not None else None
        if gap is not None and gap < IGNITION_REFRACTORY_SECONDS:
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
            "trace_ids": [str(item).strip() for item in (trace_ids or []) if str(item).strip()],
        },
    )


def _last_pulse_dt(events: list[dict[str, Any]]) -> datetime | None:
    """The timestamp of the last pulse of any kind — ignition OR idle. Both reset
    the calm clock; you don't potter right after you've just done something."""
    latest: datetime | None = None
    for event in events:
        if str(event.get("event_type") or "").strip() not in {"ignition_fired", "idle_fired"}:
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


def check_settling(memory_dir: Path, *, now: Any = None, reactivity: float = 1.0) -> dict[str, Any]:
    """Decide whether the lull has lasted long enough to invite a quiet, inward
    pulse — the mirror of ignition. True only when arousal is genuinely calm and
    it has been settled for REPOSE_THRESHOLD_SECONDS since the last pulse.

    ``reactivity`` scales arousal the same way ignition sees it, so a sleepy
    resident at night (low wakefulness) drops below the repose ceiling and settles
    — into rest or a quiet bit of making — rather than hanging in limbo.
    """
    now_iso = _as_now_iso(now)
    now_dt = _parse_dt(now_iso) or _utc_now_dt()
    events = load_runtime_events(memory_dir)
    arousal = derive_arousal(events, now=now_iso)
    effective = round(arousal["level"] * max(0.0, float(reactivity)), 4)
    clock_start = _last_pulse_dt(events) or _earliest_dt(events) or now_dt
    calm_seconds = max(0.0, (now_dt - clock_start).total_seconds())
    settle = (effective < REPOSE_AROUSAL_CEILING) and (calm_seconds >= REPOSE_THRESHOLD_SECONDS)
    return {
        "settle": bool(settle),
        "calm_seconds": round(calm_seconds, 1),
        "arousal_level": arousal["level"],
        "effective_level": effective,
        "ceiling": REPOSE_AROUSAL_CEILING,
        "threshold": REPOSE_THRESHOLD_SECONDS,
        "computed_at": now_iso,
    }


def check_fervor(memory_dir: Path, *, now: Any = None, reactivity: float = 1.0) -> dict[str, Any]:
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
    events = load_runtime_events(memory_dir)
    arousal = derive_arousal(events, now=now_iso)
    effective = round(arousal["level"] * max(0.0, float(reactivity)), 4)
    clock_start = _last_pulse_dt(events) or _earliest_dt(events) or now_dt
    restless_seconds = max(0.0, (now_dt - clock_start).total_seconds())
    fire = (FERVOR_AROUSAL_FLOOR <= effective < IGNITION_THRESHOLD) and (restless_seconds >= FERVOR_THRESHOLD_SECONDS)
    return {
        "fire": bool(fire),
        "restless_seconds": round(restless_seconds, 1),
        "arousal_level": arousal["level"],
        "effective_level": effective,
        "floor": FERVOR_AROUSAL_FLOOR,
        "threshold": FERVOR_THRESHOLD_SECONDS,
        "computed_at": now_iso,
    }


def record_idle(memory_dir: Path, *, now: Any = None) -> dict[str, Any]:
    """Mark a self-directed pulse (settling OR fervor), resetting the clock so the
    next one waits its full stretch. Taking the moment — restful or restless —
    spends it. (Arousal is left untouched: a fervor doesn't reset the buzz, so a
    still-wound resident will fervor again after another stretch.)"""
    now_iso = _as_now_iso(now)
    return append_runtime_event(memory_dir, event_type="idle_fired", payload={"fired_ts": now_iso})
