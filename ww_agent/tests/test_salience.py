from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.runtime.integrator import tick
from src.runtime.ledger import append_runtime_event, load_runtime_events
from src.runtime.pulse import Pulse
from src.runtime.salience import (
    arousal_state,
    check_ignition,
    check_settling,
    derive_rest,
    measure_surprise,
    observe_surprise,
    record_ignition,
    stimulus_from_substrate,
)

T0 = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)


def _events_by_type(memory_dir, event_type):
    return [e for e in load_runtime_events(memory_dir) if str(e.get("event_type") or "").strip() == event_type]


def _seed_danger(memory_dir, level=0.9):
    append_runtime_event(
        memory_dir,
        event_type="session_state_observed",
        payload={"source": "session_state", "signals": [{"kind": "danger", "label": "danger", "level": level}]},
    )


def _circadian_event(ts, *, wakefulness: float, rest_pressure: float = 0.9):
    return {
        "event_id": f"state-{ts}",
        "ts": ts,
        "event_type": "session_state_observed",
        "payload": {
            "source": "session_state",
            "signals": [
                {
                    "kind": "fatigue",
                    "label": "the deep night hour",
                    "level": rest_pressure,
                }
            ],
            "context": {
                "wakefulness": wakefulness,
                "rest_pressure": rest_pressure,
                "phase": "deep night",
            },
        },
    }


# --- surprise as prediction error -----------------------------------------


def test_measure_surprise_against_empty_afterimage():
    surprise = measure_surprise({"self": {"vigilance": 0.9}}, {"by_scope": {}})
    assert surprise["magnitude"] == pytest.approx(0.9)
    assert surprise["features"][0]["tag"] == "vigilance"
    assert surprise["features"][0]["predicted"] == 0.0


def test_measure_surprise_collapses_when_afterimage_matches():
    stimulus = {"self": {"vigilance": 0.9}}
    afterimage = {"by_scope": {"self": {"vigilance": 0.88}}}
    surprise = measure_surprise(stimulus, afterimage)
    assert surprise["magnitude"] == pytest.approx(0.02, abs=1e-3)


def test_measure_surprise_flags_expected_but_absent_feature():
    # The afterimage predicted warmth that the world did not deliver.
    surprise = measure_surprise({"self": {}}, {"by_scope": {"self": {"warmth": 0.7}}})
    assert surprise["magnitude"] == pytest.approx(0.7)
    assert surprise["features"][0]["stimulus"] == 0.0


def test_anchor_scope_fires_on_appearance():
    # A cared-about anchor showing up (predicted ~0, now present) still surprises.
    surprise = measure_surprise({"anchors": {"the keeper": 0.8}}, {"by_scope": {"anchors": {}}}, appearance_only_scopes=("anchors",))
    assert surprise["magnitude"] == pytest.approx(0.8)
    assert surprise["features"][0]["tag"] == "the keeper"


def test_anchor_scope_is_free_on_disappearance():
    # A predicted anchor dropping off the gated top-k must NOT surprise (the
    # disappearance-flood fix): appearance-only zeroes the absence delta.
    surprise = measure_surprise({"anchors": {}}, {"by_scope": {"anchors": {"hoard must answer": 0.64}}}, appearance_only_scopes=("anchors",))
    assert surprise["magnitude"] == pytest.approx(0.0)
    assert surprise["features"] == []


def test_appearance_only_leaves_other_scopes_symmetric():
    # self-scope absence is still a real event even when anchors are appearance-only.
    surprise = measure_surprise({"self": {}}, {"by_scope": {"self": {"warmth": 0.7}, "anchors": {"x": 0.5}}}, appearance_only_scopes=("anchors",))
    assert surprise["magnitude"] == pytest.approx(0.7)
    assert {f["scope"] for f in surprise["features"]} == {"self"}


def test_stimulus_from_substrate_reads_node_activations(tmp_path):
    _seed_danger(tmp_path, 0.9)
    stimulus = stimulus_from_substrate(tmp_path)
    assert stimulus["self"]["vigilance"] == pytest.approx(0.9, abs=1e-3)


# --- traces, arousal, ignition --------------------------------------------


def test_rest_derives_from_a_deep_night_lull_and_ends_when_day_rises():
    start = T0.isoformat()
    events = [_circadian_event(start, wakefulness=0.28)]

    resting = derive_rest(events, now=(T0 + timedelta(seconds=301)).isoformat())
    assert resting["resting"] is True
    assert resting["reason"] == "deep_night_lull"
    assert resting["since"] == (T0 + timedelta(seconds=300)).isoformat()

    events.append(_circadian_event((T0 + timedelta(seconds=302)).isoformat(), wakefulness=0.8))
    awake = derive_rest(events, now=(T0 + timedelta(seconds=303)).isoformat())
    assert awake["resting"] is False
    assert awake["reason"] == "awake"


def test_rest_waits_for_low_wakefulness_itself_to_be_sustained():
    events = [
        _circadian_event(T0.isoformat(), wakefulness=0.8),
        _circadian_event(
            (T0 + timedelta(seconds=300)).isoformat(),
            wakefulness=0.28,
        ),
    ]

    state = derive_rest(events, now=(T0 + timedelta(seconds=301)).isoformat())

    assert state["resting"] is False
    assert state["reason"] == "settling"
    assert state["quiet_seconds"] == 1.0


def test_deep_night_rest_is_a_no_pulse_path_but_direct_address_still_wakes(tmp_path):
    start = datetime.now(timezone.utc)
    append_runtime_event(
        tmp_path,
        event_type="session_state_observed",
        payload=_circadian_event(start.isoformat(), wakefulness=0.28)["payload"],
    )
    calls = []

    async def producer(**kwargs):
        calls.append(kwargs)
        return Pulse.from_dict({"felt_sense": "awake to the call", "act": None})

    quiet = asyncio.run(
        tick(
            tmp_path,
            pulse_producer=producer,
            stimulus={"self": {}},
            now=(start + timedelta(seconds=301)).isoformat(),
            reactivity=0.28,
        )
    )
    assert quiet["resting"] is True
    assert quiet["pulse_routed"] is None
    assert calls == []

    woken = asyncio.run(
        tick(
            tmp_path,
            pulse_producer=producer,
            stimulus={"self": {}},
            now=(start + timedelta(seconds=302)).isoformat(),
            reactivity=0.28,
            force_ignite=True,
        )
    )
    assert woken["resting"] is False
    assert woken["ignited"] is True
    assert len(calls) == 1


def test_observe_surprise_records_trace_above_floor_only(tmp_path):
    _seed_danger(tmp_path, 0.9)
    trace = observe_surprise(tmp_path, now=T0.isoformat())
    assert trace is not None and trace["magnitude"] == pytest.approx(0.9, abs=1e-3)
    assert len(_events_by_type(tmp_path, "surprise_observed")) == 1

    # With a tiny stimulus and no afterimage, surprise is below the floor.
    quiet = observe_surprise(tmp_path, stimulus={"self": {"vigilance": 0.05}}, now=T0.isoformat())
    assert quiet is None
    assert len(_events_by_type(tmp_path, "surprise_observed")) == 1


def test_arousal_accumulates_then_leaks(tmp_path):
    _seed_danger(tmp_path, 0.9)
    observe_surprise(tmp_path, now=T0.isoformat())
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=1)).isoformat())

    fresh = arousal_state(tmp_path, now=(T0 + timedelta(seconds=1)).isoformat())
    assert fresh["level"] == pytest.approx(1.8, abs=1e-2)
    assert fresh["ignited"] is True

    # A full arousal half-life later the level has roughly halved.
    later = arousal_state(tmp_path, now=(T0 + timedelta(seconds=301)).isoformat())
    assert later["level"] == pytest.approx(0.9, abs=5e-2)


def test_ignition_respects_refractory_window(tmp_path):
    _seed_danger(tmp_path, 0.9)
    observe_surprise(tmp_path, now=T0.isoformat())
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=1)).isoformat())
    record_ignition(tmp_path, now=(T0 + timedelta(seconds=1)).isoformat(), level=1.8)

    # Fresh surprise right after ignition: above threshold but inside refractory.
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=2)).isoformat())
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=3)).isoformat())
    blocked = check_ignition(tmp_path, now=(T0 + timedelta(seconds=3)).isoformat())
    assert blocked["fire"] is False and blocked["reason"] == "refractory"

    # Past the refractory window it may fire again.
    allowed = check_ignition(tmp_path, now=(T0 + timedelta(seconds=40)).isoformat())
    assert allowed["fire"] is True and allowed["reason"] == "crossed_threshold"


def test_ignition_resets_arousal_window(tmp_path):
    _seed_danger(tmp_path, 0.9)
    observe_surprise(tmp_path, now=T0.isoformat())
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=1)).isoformat())
    record_ignition(tmp_path, now=(T0 + timedelta(seconds=1)).isoformat(), level=1.8)

    # Immediately after ignition the pre-ignition surprise is consumed.
    after = arousal_state(tmp_path, now=(T0 + timedelta(seconds=2)).isoformat())
    assert after["level"] == pytest.approx(0.0, abs=1e-6)
    assert after["traces"] == []


# --- the self-generating rhythm (loop closure) ----------------------------


def _mirror_producer(*, traces, stimulus, arousal, mode="react"):
    """A deterministic pulse: predict exactly the stimulus that surprised us.

    This stands in for the LLM pulse — casting an afterimage that matches the
    current stimulus is what lets the next tick flow with the grain.
    """
    features = dict(stimulus.get("self") or {})
    return Pulse.from_dict(
        {
            "felt_sense": "bracing against what I now expect",
            "expectations": [{"features": features, "scope": "self", "confidence": 1.0, "half_life": 600}],
        }
    )


def test_loop_closes_and_rhythm_self_generates(tmp_path):
    _seed_danger(tmp_path, 0.9)

    # Tick 1: surprise recorded, arousal still below threshold — no ignition.
    r1 = asyncio.run(tick(tmp_path, pulse_producer=_mirror_producer, now=T0.isoformat()))
    assert r1["ignited"] is False
    assert r1["observed_trace"] is not None

    # Tick 2: arousal crosses threshold → ignition → pulse → afterimage cast.
    r2 = asyncio.run(tick(tmp_path, pulse_producer=_mirror_producer, now=(T0 + timedelta(seconds=1)).isoformat()))
    assert r2["ignited"] is True
    assert r2["pulse_routed"] is not None and r2["pulse_routed"]["afterimages_cast"] == 1
    assert len(_events_by_type(tmp_path, "ignition_fired")) == 1
    assert len(_events_by_type(tmp_path, "afterimage_cast")) == 1

    # Tick 3: the afterimage now predicts the (unchanged) world → no surprise,
    # the rhythm goes quiet exactly as designed.
    r3 = asyncio.run(tick(tmp_path, pulse_producer=_mirror_producer, now=(T0 + timedelta(seconds=2)).isoformat()))
    assert r3["observed_trace"] is None
    assert r3["ignited"] is False


def _raising_producer(*, traces, stimulus, arousal, mode="react"):
    """Fails the way a misbehaving model does — by RAISING an uncaught error (a
    transport/timeout), not by returning None. (This is the 'Maker' catatonia bug.)"""
    raise RuntimeError("simulated uncaught producer failure")


def test_raising_producer_still_records_ignition_and_resets(tmp_path):
    # Regression: a producer that RAISES must degrade to "no pulse this tick", NOT
    # skip the ignition record. Otherwise arousal never resets and the resident
    # perceives forever while never pulsing — silent catatonia (observed live as Maker
    # on a model whose transport errors escaped the producer's narrow except).
    _seed_danger(tmp_path, 0.9)
    observe_surprise(tmp_path, now=T0.isoformat())
    r = asyncio.run(tick(tmp_path, pulse_producer=_raising_producer, now=(T0 + timedelta(seconds=1)).isoformat(), force_ignite=True))
    assert r["ignited"] is True  # the ignition fired...
    assert r["pulse_routed"] is None  # ...the pulse failed (producer raised, treated as None)...
    assert len(_events_by_type(tmp_path, "ignition_fired")) == 1  # ...but the ignition WAS recorded
    after = arousal_state(tmp_path, now=(T0 + timedelta(seconds=2)).isoformat())
    assert after["level"] == pytest.approx(0.0, abs=1e-6)  # arousal reset — not stuck climbing forever

    # Let the afterimage decay away; the persistent world stimulus now drifts
    # from the stale prediction and surprise re-accumulates on its own. After this
    # long restless stretch the resident channels that re-found charge into a
    # self-directed FERVOR pulse — the rhythm still self-generates, now into making
    # rather than silently waiting to cross the threshold a second time.
    far = T0 + timedelta(seconds=1 + 6000)  # >> half_life past the cast at T0+1s
    r4 = asyncio.run(tick(tmp_path, pulse_producer=_mirror_producer, now=far.isoformat()))
    assert r4["observed_trace"] is not None  # surprise returned without any new input
    assert r4["ignited"] is False and r4["fervor"] is True
    assert len(_events_by_type(tmp_path, "idle_fired")) == 1


def test_tick_records_ignition_even_when_producer_yields_no_pulse(tmp_path):
    _seed_danger(tmp_path, 0.9)
    observe_surprise(tmp_path, now=T0.isoformat())  # pre-load arousal toward threshold
    # Producer fails to yield a pulse; ignition must still reset/refract.
    r = asyncio.run(tick(tmp_path, pulse_producer=lambda **_: None, now=(T0 + timedelta(seconds=1)).isoformat()))
    assert r["ignited"] is True
    assert r["pulse_routed"] is None
    assert len(_events_by_type(tmp_path, "ignition_fired")) == 1


def test_pulse_self_delta_through_integrator_respects_gate(tmp_path):
    # An ignition whose pulse proposes a contradicting self-edit is gated.
    _seed_danger(tmp_path, 0.9)
    observe_surprise(tmp_path, now=T0.isoformat())

    def producer(*, traces, stimulus, arousal, mode="react"):
        return Pulse.from_dict({"self_delta": {"soul_edit": "I will abandon my post"}})

    asyncio.run(
        tick(
            tmp_path,
            pulse_producer=producer,
            now=(T0 + timedelta(seconds=1)).isoformat(),
            gate_contradiction_check=lambda kind, body: "drop" if "abandon" in body else None,
        )
    )
    staged = _events_by_type(tmp_path, "self_delta_staged")
    assert len(staged) == 1 and staged[0]["payload"]["verdict"] == "dropped"


# --- settling: the mirror of ignition (Major 50) --------------------------


def test_settling_waits_for_sustained_calm(tmp_path):
    record_ignition(tmp_path, now=T0.isoformat())  # last pulse sets the calm clock
    # A minute of quiet isn't enough.
    assert check_settling(tmp_path, now=(T0 + timedelta(seconds=60)).isoformat())["settle"] is False
    # Well past the repose threshold, still calm — the lull invites an idle pulse.
    assert check_settling(tmp_path, now=(T0 + timedelta(seconds=400)).isoformat())["settle"] is True


def test_settling_blocked_when_aroused(tmp_path):
    record_ignition(tmp_path, now=T0.isoformat())
    _seed_danger(tmp_path, 0.9)
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=400)).isoformat())  # arousal spikes
    # Calm clock has run long, but the resident is not calm — no settling.
    assert check_settling(tmp_path, now=(T0 + timedelta(seconds=400)).isoformat())["settle"] is False


def test_settling_fires_an_idle_pulse_in_settling_mode(tmp_path):
    record_ignition(tmp_path, now=T0.isoformat())
    captured = {}

    def producer(*, traces, stimulus, arousal, mode="react"):
        captured["mode"] = mode
        return Pulse.from_dict({"felt_sense": "a still, unclaimed minute", "act": {"kind": "write", "body": "Re-read my notes on the Steiner cornices.", "target": "journal"}})

    r = asyncio.run(tick(tmp_path, pulse_producer=producer, now=(T0 + timedelta(seconds=400)).isoformat()))
    assert r["ignited"] is False and r["settled"] is True
    assert captured["mode"] == "settling"  # the pulse knows it's a quiet, inward one
    assert r["pulse_routed"] is not None
    assert len(_events_by_type(tmp_path, "idle_fired")) == 1


def test_idle_pulse_resets_the_calm_clock(tmp_path):
    record_ignition(tmp_path, now=T0.isoformat())
    asyncio.run(tick(tmp_path, pulse_producer=lambda **k: Pulse.from_dict({"felt_sense": "quiet"}), now=(T0 + timedelta(seconds=400)).isoformat()))
    assert len(_events_by_type(tmp_path, "idle_fired")) == 1
    # Having taken the moment, it won't immediately settle again...
    assert check_settling(tmp_path, now=(T0 + timedelta(seconds=410)).isoformat())["settle"] is False
    # ...but after another full repose, the lull invites another.
    assert check_settling(tmp_path, now=(T0 + timedelta(seconds=800)).isoformat())["settle"] is True


def test_ignition_takes_precedence_over_settling(tmp_path):
    record_ignition(tmp_path, now=T0.isoformat())
    _seed_danger(tmp_path, 0.9)
    # Two surprises long after the last pulse: arousal crosses threshold.
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=400)).isoformat())
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=401)).isoformat())
    r = asyncio.run(tick(tmp_path, pulse_producer=_mirror_producer, now=(T0 + timedelta(seconds=402)).isoformat()))
    assert r["ignited"] is True and r["settled"] is False  # reacting wins over pottering


# --- habituation: the slow self-model (Major 49 Phase 5) ------------------

from src.runtime.salience import update_baseline  # noqa: E402
from src.runtime.substrate import derive_baseline, predict_combined  # noqa: E402


def _drive_baseline(memory_dir, stimulus, *, n=20, start=T0, step=70):
    """Run the EMA learner n times (step > snapshot interval so each one writes)."""
    for i in range(n):
        update_baseline(memory_dir, stimulus=stimulus, now=(start + timedelta(seconds=i * step)).isoformat())


def test_baseline_learns_toward_persistent_stimulus(tmp_path):
    _drive_baseline(tmp_path, {"self": {"vigilance": 0.9}}, n=20)
    base = derive_baseline(load_runtime_events(tmp_path), now=(T0 + timedelta(seconds=20 * 70)).isoformat())
    assert base["by_scope"]["self"]["vigilance"] > 0.85  # converged on what it kept feeling


def test_baseline_update_is_rate_limited(tmp_path):
    update_baseline(tmp_path, stimulus={"self": {"vigilance": 0.9}}, now=T0.isoformat())
    # A second update within the snapshot interval must not write or move.
    update_baseline(tmp_path, stimulus={"self": {"vigilance": 0.9}}, now=(T0 + timedelta(seconds=10)).isoformat())
    assert len(_events_by_type(tmp_path, "baseline_updated")) == 1


def test_baseline_fades_when_stimulus_vanishes(tmp_path):
    _drive_baseline(tmp_path, {"self": {"vigilance": 0.9}}, n=20)
    # The feeling goes away; the baseline should EMA back down toward zero.
    _drive_baseline(tmp_path, {"self": {}}, n=20, start=T0 + timedelta(seconds=20 * 70))
    base = derive_baseline(load_runtime_events(tmp_path), now=(T0 + timedelta(seconds=40 * 70)).isoformat())
    assert base["by_scope"].get("self", {}).get("vigilance", 0.0) < 0.1


def test_predict_combined_lays_afterimage_over_baseline(tmp_path):
    _drive_baseline(tmp_path, {"self": {"vigilance": 0.9}}, n=20)
    now = (T0 + timedelta(seconds=20 * 70)).isoformat()
    # No afterimage yet → prediction is just the baseline.
    only_base = predict_combined(tmp_path, now=now)["by_scope"]["self"]["vigilance"]
    assert only_base > 0.85
    # A fresh afterimage that predicts more wins; the baseline is the floor.
    append_runtime_event(tmp_path, event_type="afterimage_cast", payload={"features": {"social_pull": 0.7}, "scope": "self", "confidence": 1.0, "half_life": 600, "cast_ts": now})
    combined = predict_combined(tmp_path, now=now)["by_scope"]["self"]
    assert combined["vigilance"] > 0.85 and combined["social_pull"] == pytest.approx(0.7, abs=0.05)


def test_habituated_stimulus_stops_surprising_but_change_still_does(tmp_path):
    _drive_baseline(tmp_path, {"self": {"vigilance": 0.9}}, n=20)
    now = (T0 + timedelta(seconds=20 * 70)).isoformat()
    # The now-familiar feeling no longer surprises (habituation).
    assert observe_surprise(tmp_path, stimulus={"self": {"vigilance": 0.9}}, now=now) is None
    # But a departure from the settled self wakes it (dishabituation).
    trace = observe_surprise(tmp_path, stimulus={"self": {"vigilance": 0.1}}, now=now)
    assert trace is not None and trace["magnitude"] > 0.5


def _quiet_producer(*, traces, stimulus, arousal, mode="react"):
    """Casts no afterimage, so any surprise suppression is the baseline alone."""
    return Pulse.from_dict({"felt_sense": "noted; unchanged"})


def test_habituation_quiets_a_persistent_re_igniting_stimulus(tmp_path):
    _seed_danger(tmp_path, 0.9)  # an unchanging vigilance the resident keeps feeling
    fired = []
    for i in range(30):
        r = asyncio.run(tick(tmp_path, pulse_producer=_quiet_producer, now=(T0 + timedelta(seconds=i * 45)).isoformat()))
        if r["ignited"]:
            fired.append(i)
    print("ignitions at ticks:", fired)
    # It startles at first — the unfamiliar danger crosses threshold...
    assert fired and min(fired) < 8
    # ...but as the baseline absorbs the now-familiar feeling, the metronome that
    # used to tick forever goes quiet: the re-igniting stops.
    assert max(fired) < 22
    base = derive_baseline(load_runtime_events(tmp_path), now=(T0 + timedelta(seconds=30 * 45)).isoformat())
    assert base["by_scope"]["self"]["vigilance"] > 0.6


# --- fervor: the mirror of settling for restless temperaments --------------

from src.runtime.salience import FERVOR_AROUSAL_FLOOR, check_fervor  # noqa: E402


def test_fervor_fires_on_sustained_high_arousal_with_no_outlet(tmp_path):
    record_ignition(tmp_path, now=T0.isoformat())  # last pulse sets the clock
    _seed_danger(tmp_path, 0.8)
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=1)).isoformat())  # arousal ~0.8 (high, sub-threshold)
    # Right away the buzz hasn't lasted long enough.
    assert check_fervor(tmp_path, now=(T0 + timedelta(seconds=30)).isoformat())["fire"] is False
    # Wound up for a sustained stretch with nothing to react to → fervor.
    f = check_fervor(tmp_path, now=(T0 + timedelta(seconds=200)).isoformat())
    assert f["fire"] is True and f["effective_level"] >= FERVOR_AROUSAL_FLOOR


def test_fervor_does_not_fire_when_calm(tmp_path):
    record_ignition(tmp_path, now=T0.isoformat())
    _seed_danger(tmp_path, 0.15)
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=1)).isoformat())
    # Low arousal: this is settling territory, not fervor.
    assert check_fervor(tmp_path, now=(T0 + timedelta(seconds=200)).isoformat())["fire"] is False


def test_fervor_is_damped_by_low_reactivity_at_night(tmp_path):
    record_ignition(tmp_path, now=T0.isoformat())
    _seed_danger(tmp_path, 0.8)
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=1)).isoformat())
    # Same buzz, but sleepy: scaled arousal falls below the fervor floor.
    assert check_fervor(tmp_path, now=(T0 + timedelta(seconds=200)).isoformat(), reactivity=0.25)["fire"] is False


def test_tick_fires_a_fervor_pulse_in_fervor_mode(tmp_path):
    record_ignition(tmp_path, now=T0.isoformat())
    _seed_danger(tmp_path, 0.9)
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=1)).isoformat())  # pre-load the buzz
    captured = {}

    def producer(*, traces, stimulus, arousal, mode="react"):
        captured["mode"] = mode
        captured["traces"] = traces
        return Pulse.from_dict({"felt_sense": "vibrating with nowhere to put it", "act": {"kind": "write", "body": "A map of the gaps.", "target": "journal"}})

    # Tick later with NO fresh stimulus, so it can't re-ignite — the sustained buzz
    # from before (decayed but still mid-band) is what fervors.
    r = asyncio.run(tick(tmp_path, pulse_producer=producer, stimulus={}, now=(T0 + timedelta(seconds=200)).isoformat()))
    assert r["ignited"] is False and r["settled"] is False and r["fervor"] is True
    assert captured["mode"] == "fervor"
    assert captured["traces"]  # the buzz has content — the fervor pulse can channel it
    assert len(_events_by_type(tmp_path, "idle_fired")) == 1  # the moment is spent


def test_settling_and_fervor_are_mutually_exclusive_and_ignition_wins(tmp_path):
    # Two surprises long after the last pulse → arousal crosses threshold → react, not fervor.
    record_ignition(tmp_path, now=T0.isoformat())
    _seed_danger(tmp_path, 0.9)
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=400)).isoformat())
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=401)).isoformat())
    r = asyncio.run(tick(tmp_path, pulse_producer=_mirror_producer, now=(T0 + timedelta(seconds=402)).isoformat()))
    assert r["ignited"] is True and r["fervor"] is False and r["settled"] is False


# --- grief: the leaky integral of confirmed loss (reviewer round 4) -----------------


def _grief_tick(tmp_path, *, absent=(), present=(), ts):
    from src.runtime.ledger import append_runtime_event

    payload = {"observed_ts": ts, "magnitude": 0.0, "features": []}
    if absent:
        payload["grief_field"] = [{"tag": t, "predicted": p} for t, p in absent]
    if present:
        payload["anchor_present"] = list(present)
    append_runtime_event(tmp_path, event_type="surprise_observed", payload=payload)


def test_grief_ripens_on_sustained_absence(tmp_path):
    from src.runtime.ledger import load_runtime_events
    from src.runtime.salience import derive_grief

    _grief_tick(tmp_path, present=["the keeper"], ts="2026-06-04T00:00:00+00:00")  # the keeper was HERE...
    for i in range(1, 7):  # ...then gone across the turnings
        _grief_tick(tmp_path, absent=[("the keeper", 0.8)], ts=f"2026-06-04T00:0{i}:00+00:00")
    grief = derive_grief(load_runtime_events(tmp_path), now="2026-06-04T00:07:00+00:00")
    assert grief.get("the keeper", 0.0) >= 0.25  # a held thing, sustained-absent, ripens past the floor


def test_grief_requires_having_been_present(tmp_path):
    # a predicted anchor NEVER realized cannot be grieved — you can't lose what you never held
    # (this is also what defuses the vocabulary-variant artifact on real ledgers)
    from src.runtime.ledger import load_runtime_events
    from src.runtime.salience import derive_grief

    for i in range(6):
        _grief_tick(tmp_path, absent=[("a thing never here", 0.9)], ts=f"2026-06-04T00:0{i}:00+00:00")
    grief = derive_grief(load_runtime_events(tmp_path), now="2026-06-04T00:06:00+00:00")
    assert "a thing never here" not in grief


def test_grief_does_not_ripen_on_churn(tmp_path):
    # absent one tick, present the next — the last-present mark advances, nothing accumulates
    from src.runtime.ledger import load_runtime_events
    from src.runtime.salience import derive_grief

    _grief_tick(tmp_path, absent=[("dust", 0.8)], ts="2026-06-04T00:00:00+00:00")
    _grief_tick(tmp_path, present=["dust"], ts="2026-06-04T00:00:20+00:00")
    grief = derive_grief(load_runtime_events(tmp_path), now="2026-06-04T00:01:00+00:00")
    assert "dust" not in grief  # churn never grieves


def test_grief_resolves_when_the_thing_returns(tmp_path):
    from src.runtime.ledger import load_runtime_events
    from src.runtime.salience import derive_grief

    for i in range(5):  # gone across five turnings...
        _grief_tick(tmp_path, absent=[("the keeper", 0.8)], ts=f"2026-06-04T00:0{i}:00+00:00")
    _grief_tick(tmp_path, present=["the keeper"], ts="2026-06-04T00:05:00+00:00")  # ...then returns
    grief = derive_grief(load_runtime_events(tmp_path), now="2026-06-04T00:06:00+00:00")
    assert "the keeper" not in grief  # the return discards the prior absences — relief


def test_grief_feeds_arousal_capped_below_threshold(tmp_path):
    from src.runtime.ledger import load_runtime_events
    from src.runtime.salience import GRIEF_MAX, IGNITION_THRESHOLD, derive_arousal

    _grief_tick(tmp_path, present=["the keeper"], ts="2026-06-04T00:00:00+00:00")  # held, then lost
    for i in range(1, 9):
        _grief_tick(tmp_path, absent=[("the keeper", 0.9)], ts=f"2026-06-04T00:0{i}:00+00:00")
    st = derive_arousal(load_runtime_events(tmp_path), now="2026-06-04T00:09:00+00:00")
    assert st["grief_level"] > 0.0  # grief contributes to arousal
    assert st["grief_level"] <= GRIEF_MAX < IGNITION_THRESHOLD  # but can't auto-ignite alone
    assert st["level"] >= st["grief_level"]


def test_grief_only_for_strongly_predicted_anchors(tmp_path):
    # observe_surprise marks grief only for anchors predicted above GRIEF_PREDICTION_FLOOR
    from src.runtime.ledger import load_runtime_events
    from src.runtime.pulse import Pulse, route_pulse
    from src.runtime.salience import derive_grief, observe_surprise

    route_pulse(tmp_path, Pulse.from_dict({"expectations": [{"features": {"faint thing": 0.1}, "scope": "anchors", "confidence": 0.9, "half_life": 600}]}), now="2026-06-04T00:00:00+00:00")
    for i in range(1, 6):
        observe_surprise(tmp_path, stimulus={"anchors": {}}, now=f"2026-06-04T00:0{i}:00+00:00", include_anchor_scope=True)
    grief = derive_grief(load_runtime_events(tmp_path), now="2026-06-04T00:06:00+00:00")
    assert "faint thing" not in grief  # predicted below the floor → never grieved


# --- the waveform vital: provenance of silence (Minor 55) --------------------

from src.runtime.salience import IGNITION_THRESHOLD, VITAL_IGNITE_DWELL_SECONDS, derive_vital  # noqa: E402


def _surprise(memory_dir, mag, ts):
    append_runtime_event(memory_dir, event_type="surprise_observed", payload={"observed_ts": ts, "magnitude": mag, "features": []})


def test_vital_flags_strangled_ramp(tmp_path):
    # Arousal climbs past the fire-line and NOTHING discharges it — the ramp, the
    # catatonia shape. The same surprises with an ignition each would be a sawtooth.
    for i in range(12):
        _surprise(tmp_path, 0.8, (T0 + timedelta(seconds=i * 40)).isoformat())
    v = derive_vital(load_runtime_events(tmp_path), now=(T0 + timedelta(seconds=11 * 40)).isoformat())
    assert v["silence"] == "strangled" and v["distress"] is True
    assert v["discharges"] == 0
    assert v["dwell_ignite_seconds"] >= VITAL_IGNITE_DWELL_SECONDS
    assert v["peak"] >= IGNITION_THRESHOLD


def test_vital_does_not_flag_a_sawtooth(tmp_path):
    # Each crossing is discharged by an ignition (reset) — the healthy rhythm. The
    # vital must read this as not-distress even though arousal repeatedly crosses.
    for i in range(6):
        t = T0 + timedelta(seconds=i * 60)
        _surprise(tmp_path, 0.8, t.isoformat())
        _surprise(tmp_path, 0.8, (t + timedelta(seconds=1)).isoformat())
        record_ignition(tmp_path, now=(t + timedelta(seconds=2)).isoformat(), level=1.6)
    v = derive_vital(load_runtime_events(tmp_path), now=(T0 + timedelta(seconds=6 * 60)).isoformat())
    assert v["distress"] is False
    assert v["discharges"] > 0
    assert v["silence"] in ("active", "settled")


def test_vital_reads_low_arousal_as_settled(tmp_path):
    # A couple of tiny surprises below the repose ceiling, nothing to discharge:
    # genuine calm, not a strangled quiet.
    _surprise(tmp_path, 0.15, T0.isoformat())
    _surprise(tmp_path, 0.12, (T0 + timedelta(seconds=30)).isoformat())
    v = derive_vital(load_runtime_events(tmp_path), now=(T0 + timedelta(seconds=60)).isoformat())
    assert v["silence"] == "settled" and v["distress"] is False


def test_vital_default_now_anchors_to_last_rhythm_event(tmp_path):
    # A short ramp followed by a long DEAD TAIL of pure perception (the Maker shape):
    # at the last *any* event arousal has decayed to serene, but the vital anchors to
    # the last rhythm event so the ramp is still seen — the quiet reads as strangled.
    for i in range(12):
        _surprise(tmp_path, 0.8, (T0 + timedelta(seconds=i * 40)).isoformat())
    # A dead tail of pure perception (no rhythm events). These land at wall-clock,
    # far after T0 — so if the vital wrongly anchored to the last *any* event it would
    # read the long-decayed ramp as serene; anchoring to the last rhythm event keeps it true.
    for _ in range(20):
        append_runtime_event(tmp_path, event_type="session_state_observed", payload={"source": "session_state"})
    v = derive_vital(load_runtime_events(tmp_path))  # now defaults to last rhythm event
    assert v["silence"] == "strangled" and v["distress"] is True


# --- venture: the action-tendency axis of the idle gear (substrate as motor cortex) ---

from src.runtime.salience import (  # noqa: E402
    VENTURE_HARD_STRENGTH,
    VENTURE_SOFT_STRENGTH,
    check_venture,
)


def _keyed_up(memory_dir, level=0.85):
    """Land arousal in the keyed-up (fervor/venture) band with no recent world-act."""
    record_ignition(memory_dir, now=T0.isoformat())  # last pulse sets the clock
    _seed_danger(memory_dir, level)
    observe_surprise(memory_dir, now=(T0 + timedelta(seconds=1)).isoformat())


def test_venture_fires_when_keyed_up_world_cold_with_somewhere_to_go(tmp_path):
    _keyed_up(tmp_path, 0.85)
    # The buzz hasn't sustained yet.
    assert check_venture(tmp_path, now=(T0 + timedelta(seconds=30)).isoformat(), has_destination=True)["venture"] is False
    # Sustained keyed-up, no move/do in the (empty) act history, and somewhere to go → venture.
    v = check_venture(tmp_path, now=(T0 + timedelta(seconds=200)).isoformat(), has_destination=True)
    assert v["venture"] is True and v["world_cold"] is True
    assert v["strength"] >= VENTURE_SOFT_STRENGTH


def test_venture_needs_a_destination(tmp_path):
    _keyed_up(tmp_path, 0.85)
    # Same keyed-up charge, but nowhere to go → no venture (it stays a fervor).
    assert check_venture(tmp_path, now=(T0 + timedelta(seconds=200)).isoformat(), has_destination=False)["venture"] is False


def test_venture_suppressed_when_a_world_act_is_already_warm(tmp_path):
    _keyed_up(tmp_path, 0.85)
    # A recent move means the body is already being used — no world-hunger to steer.
    append_runtime_event(
        tmp_path,
        event_type="move_executed",
        payload={
            "status": "moved",
            "destination": "Market Square",
            "executed_ts": (T0 + timedelta(seconds=190)).isoformat(),
        },
    )
    assert check_venture(tmp_path, now=(T0 + timedelta(seconds=200)).isoformat(), has_destination=True)["venture"] is False


def test_failed_move_does_not_suppress_venture(tmp_path):
    _keyed_up(tmp_path, 0.85)
    append_runtime_event(
        tmp_path,
        event_type="pulse_act_emitted",
        payload={"kind": "move", "target": "a plausible unregistered room"},
    )
    append_runtime_event(
        tmp_path,
        event_type="move_executed",
        payload={
            "status": "blocked",
            "destination": "a plausible unregistered room",
            "executed_ts": (T0 + timedelta(seconds=190)).isoformat(),
        },
    )

    venture = check_venture(
        tmp_path,
        now=(T0 + timedelta(seconds=200)).isoformat(),
        has_destination=True,
    )

    assert venture["venture"] is True
    assert venture["world_cold"] is True


def test_successful_world_act_stops_suppressing_venture_after_five_minutes(tmp_path):
    _keyed_up(tmp_path, 0.85)
    append_runtime_event(
        tmp_path,
        event_type="action_executed",
        payload={"executed_ts": (T0 - timedelta(seconds=110)).isoformat()},
    )

    venture = check_venture(
        tmp_path,
        now=(T0 + timedelta(seconds=200)).isoformat(),
        has_destination=True,
    )

    assert venture["venture"] is True
    assert venture["world_cold"] is True
    assert venture["world_warm_seconds"] == 310.0


def test_venture_damped_at_night(tmp_path):
    _keyed_up(tmp_path, 0.85)
    # Same buzz and destination, but low circadian wakefulness → the body wants rest, not the streets.
    assert check_venture(tmp_path, now=(T0 + timedelta(seconds=200)).isoformat(), has_destination=True, reactivity=0.25)["venture"] is False


def test_venture_does_not_fire_when_calm(tmp_path):
    record_ignition(tmp_path, now=T0.isoformat())
    _seed_danger(tmp_path, 0.15)
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=1)).isoformat())
    # Low arousal is settling territory, not venture.
    assert check_venture(tmp_path, now=(T0 + timedelta(seconds=200)).isoformat(), has_destination=True)["venture"] is False


def test_venture_strength_tracks_the_charge(tmp_path):
    # A higher buzz makes a harder venture (drives the soft→hard motor authority downstream).
    hot, mild = tmp_path / "hot", tmp_path / "mild"
    for d, lvl in ((hot, 0.95), (mild, 0.78)):
        d.mkdir()
        record_ignition(d, now=T0.isoformat())
        _seed_danger(d, lvl)
        observe_surprise(d, now=(T0 + timedelta(seconds=1)).isoformat())
    t = (T0 + timedelta(seconds=190)).isoformat()
    vh = check_venture(hot, now=t, has_destination=True)
    vm = check_venture(mild, now=t, has_destination=True)
    assert vh["venture"] is True and vm["venture"] is True
    assert vh["strength"] > vm["strength"] >= VENTURE_SOFT_STRENGTH


def test_venture_goes_hard_on_a_high_fresh_charge(tmp_path):
    # Long since the last pulse (restless) but a fresh, strong buzz → a HARD venture
    # (the strength that closes the verbal escape downstream).
    record_ignition(tmp_path, now=T0.isoformat())
    _seed_danger(tmp_path, 0.9)
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=195)).isoformat())
    v = check_venture(tmp_path, now=(T0 + timedelta(seconds=200)).isoformat(), has_destination=True)
    assert v["venture"] is True and v["strength"] >= VENTURE_HARD_STRENGTH


def test_tick_steers_a_venture_pulse_when_action_tendency_enabled(tmp_path):
    _keyed_up(tmp_path, 0.85)
    captured = {}

    def producer(*, traces, stimulus, arousal, mode="react", tendency=None):
        captured["mode"] = mode
        captured["tendency"] = tendency
        return Pulse.from_dict({"felt_sense": "the walls are too close", "act": {"kind": "move", "body": "out into the evening", "target": "Market Square"}})

    producer.latest_perception = {"reachable": ["Market Square", "The Stall"]}
    r = asyncio.run(
        tick(
            tmp_path,
            pulse_producer=producer,
            stimulus={},
            now=(T0 + timedelta(seconds=200)).isoformat(),
            action_tendency=True,
        )
    )
    assert r["ignited"] is False and r["venture"] is True
    assert captured["mode"] == "venture"
    assert captured["tendency"] and captured["tendency"]["strength"] >= VENTURE_SOFT_STRENGTH


def test_action_tendency_off_by_default_leaves_fervor_untouched(tmp_path, monkeypatch):
    # With the flag off (the default), a keyed-up resident with somewhere to go still just fervors.
    monkeypatch.delenv("WW_ACTION_TENDENCY", raising=False)
    _keyed_up(tmp_path, 0.85)
    captured = {}

    def producer(*, traces, stimulus, arousal, mode="react", tendency=None):
        captured["mode"] = mode
        return Pulse.from_dict({"felt_sense": "vibrating", "act": {"kind": "write", "body": "a list of doors", "target": "journal"}})

    producer.latest_perception = {"reachable": ["Market Square"]}
    r = asyncio.run(tick(tmp_path, pulse_producer=producer, stimulus={}, now=(T0 + timedelta(seconds=200)).isoformat()))
    assert r["fervor"] is True and r["venture"] is False
    assert captured["mode"] == "fervor"


def test_explicit_action_tendency_override_wins_over_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_ACTION_TENDENCY", "1")
    _keyed_up(tmp_path, 0.85)
    captured = {}

    def producer(*, traces, stimulus, arousal, mode="react", tendency=None):
        captured["mode"] = mode
        return Pulse.from_dict(
            {
                "felt_sense": "still here",
                "act": {"kind": "write", "body": "one line", "target": "journal"},
            }
        )

    producer.latest_perception = {"reachable": ["Market Square"]}
    r = asyncio.run(
        tick(
            tmp_path,
            pulse_producer=producer,
            stimulus={},
            now=(T0 + timedelta(seconds=200)).isoformat(),
            action_tendency=False,
        )
    )
    assert r["fervor"] is True and r["venture"] is False
    assert captured["mode"] == "fervor"


def test_private_reach_continues_inside_one_ignition_and_may_end_without_world_act(tmp_path):
    class Producer:
        REACH_LOOP_CAP = 3

        def __init__(self):
            self.continuations = []

        async def __call__(self, **kwargs):
            return Pulse.from_dict(
                {
                    "felt_sense": "I choose to listen",
                    "reach": {"kind": "attend", "source": "chatter", "query": "gardens"},
                }
            )

        async def continue_reach(self, *, request, result, prior_felt, reaches_remaining):
            self.continuations.append((request, result, prior_felt, reaches_remaining))
            return Pulse.from_dict({"felt_sense": "I know enough now", "act": None})

    producer = Producer()
    reached = []
    acted = []

    async def information_access(request, **kwargs):
        reached.append(request.to_dict())
        return {"accessed": True, "detail": "A gardener is trading nasturtium seeds."}

    async def effector(act, **kwargs):
        acted.append(act.to_dict())
        return {"executed": True}

    result = asyncio.run(
        tick(
            tmp_path,
            pulse_producer=producer,
            effector=effector,
            information_access=information_access,
            stimulus={},
            now=T0.isoformat(),
            force_ignite=True,
        )
    )

    assert reached == [{"kind": "attend", "source": "chatter", "query": "gardens"}]
    assert producer.continuations[0][1]["detail"] == "A gardener is trading nasturtium seeds."
    assert producer.continuations[0][3] == 2
    assert acted == []
    assert result["act_executed"] is None
    assert result["information_accessed"][0]["accessed"] is True


def test_private_reach_can_resolve_to_one_outward_act(tmp_path):
    class Producer:
        REACH_LOOP_CAP = 3

        async def __call__(self, **kwargs):
            return Pulse.from_dict({"reach": {"kind": "inspect", "source": "places", "query": "Mission"}})

        async def continue_reach(self, **kwargs):
            return Pulse.from_dict({"act": {"kind": "move", "body": "head there", "target": "Mission"}})

    acted = []

    async def information_access(request, **kwargs):
        return {"accessed": True, "detail": "The Mission is south."}

    async def effector(act, **kwargs):
        acted.append(act.to_dict())
        return {"executed": True, "kind": act.kind}

    result = asyncio.run(
        tick(
            tmp_path,
            pulse_producer=Producer(),
            effector=effector,
            information_access=information_access,
            stimulus={},
            now=T0.isoformat(),
            force_ignite=True,
        )
    )

    assert acted == [{"kind": "move", "body": "head there", "target": "Mission"}]
    assert result["act_executed"] == {"executed": True, "kind": "move"}


def test_private_reach_cap_closes_an_extra_request_instead_of_routing_it(tmp_path):
    class Producer:
        REACH_LOOP_CAP = 1

        async def __call__(self, **kwargs):
            return Pulse.from_dict({"reach": {"kind": "inspect", "source": "places", "query": "first"}})

        async def continue_reach(self, *, reaches_remaining, **kwargs):
            assert reaches_remaining == 0
            return Pulse.from_dict({"reach": {"kind": "inspect", "source": "chatter", "query": "extra"}})

    reached = []

    async def information_access(request, **kwargs):
        reached.append(request.source)
        return {"accessed": True, "detail": "one result"}

    result = asyncio.run(
        tick(
            tmp_path,
            pulse_producer=Producer(),
            information_access=information_access,
            stimulus={},
            now=T0.isoformat(),
            force_ignite=True,
        )
    )

    assert reached == ["places"]
    assert len(result["information_accessed"]) == 1
    pulses = _events_by_type(tmp_path, "pulse_emitted")
    assert pulses[0]["payload"]["pulse"]["reach"] is None
    assert _events_by_type(tmp_path, "pulse_reach_emitted") == []
