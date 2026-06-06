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
GRIEF_PREDICTION_FLOOR = 0.2  # only grieve anchors that were predicted at least this strongly
GRIEF_HALF_LIFE_SECONDS = 600.0  # a confirmed-absence observation's weight decays this slowly
GRIEF_FLOOR = 0.25  # ripened grief below this is not yet felt (no arousal contribution)
GRIEF_GAIN = 0.5  # how strongly summed ripened grief feeds arousal
GRIEF_MAX = 0.8  # cap the grief term below IGNITION_THRESHOLD: grief makes the resident raw,
# the next small surprise tips it — grief alone never auto-ignites on a loop

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

# The self-scope feel-axes the substrate models. A world that cannot feed one of
# these (e.g. a mail-less LocalWorld and correspondence_pull) declares it muted; it
# is then dropped from both the pulse's advertised senses and the surprise scope, so
# a mind never predicts — and is never wrongly surprised by — a sense its world has.
SELF_SENSES = ("vigilance", "social_pull", "mobility_drive", "correspondence_pull", "rest_drive")

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


def measure_surprise(stimulus: Any, afterimage: Any, *, appearance_only_scopes: tuple[str, ...] = ()) -> dict[str, Any]:
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
        prediction["by_scope"] = {scope: tags for scope, tags in prediction["by_scope"].items() if scope != ANCHOR_SCOPE}
    # Capability scoping (Major 50): a sense the world cannot feed is muted — the mind
    # neither predicts it nor is surprised by it. Drop it from BOTH the prediction and
    # the stimulus. Dropping from prediction alone is enough only when the sense's
    # stimulus is structurally zero (correspondence_pull, no mail backend): predicted→0,
    # stimulus→0, no surprise. But a sense whose stimulus still FIRES (mobility_drive,
    # derived from event-pull at ~0.9 with no map to spend it on) would otherwise surprise
    # at full delta against the now-absent prediction every tick — pumping arousal stably.
    # So mute means absent from the stimulus too.
    if muted_senses:
        _pred_scopes = prediction.get("by_scope") if isinstance(prediction.get("by_scope"), dict) else {}
        _stim_scopes = stimulus if isinstance(stimulus, dict) else {}
        for scopes in (_pred_scopes, _stim_scopes):
            for tags in scopes.values():
                if isinstance(tags, dict):
                    for sense in muted_senses:
                        tags.pop(sense, None)
    # The anchor scope is appearance-weighted: a cared-about thing showing up
    # surprises; a held anchor merely dropping off the gated top-k does not (it was
    # manufacturing a disappearance-flood — see measure_surprise).
    surprise = measure_surprise(stimulus, prediction, appearance_only_scopes=(ANCHOR_SCOPE,))

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
            if pv >= GRIEF_PREDICTION_FLOOR and float(stim_anchors.get(tag, 0.0)) < FEATURE_EPSILON:
                grief_field.append({"tag": str(tag), "predicted": round(pv, 4)})
        anchor_present = [str(t) for t, v in stim_anchors.items() if float(v) >= FEATURE_EPSILON]

    if surprise["magnitude"] < SURPRISE_FLOOR and not grief_field:
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
            total += pv * (0.5 ** (age / GRIEF_HALF_LIFE_SECONDS)) if GRIEF_HALF_LIFE_SECONDS > 0 else pv
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
    return derive_arousal(load_runtime_events(memory_dir), now=now)


def igniting_traces(memory_dir: Path, *, now: Any = None) -> list[dict[str, Any]]:
    """The active traces the pulse will read on ignition."""
    return arousal_state(memory_dir, now=now)["traces"]


def check_ignition(memory_dir: Path, *, now: Any = None, reactivity: float = 1.0, refractory_seconds: float | None = None) -> dict[str, Any]:
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
    refr = IGNITION_REFRACTORY_SECONDS if refractory_seconds is None else max(0.0, float(refractory_seconds))
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
