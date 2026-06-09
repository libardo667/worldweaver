from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from src.runtime.circadian import CHRONOTYPE_SPREAD_HOURS, chronotype, circadian_state
from src.runtime.integrator import tick
from src.runtime.ledger import load_runtime_events
from src.runtime.pulse import Pulse
from src.runtime.salience import check_settling, observe_surprise, record_ignition

T0 = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)


def _events_by_type(memory_dir, event_type):
    return [e for e in load_runtime_events(memory_dir) if str(e.get("event_type") or "").strip() == event_type]


def _seed_danger(memory_dir, level=0.9):
    from src.runtime.ledger import append_runtime_event

    append_runtime_event(memory_dir, event_type="session_state_observed", payload={"source": "session_state", "signals": [{"kind": "danger", "label": "danger", "level": level}]})


# --- the curve ------------------------------------------------------------


def test_wakefulness_peaks_midafternoon_and_troughs_predawn():
    assert circadian_state(15.5)["wakefulness"] > 0.95  # mid-afternoon, fully awake
    assert circadian_state(3.5)["wakefulness"] < 0.3  # small hours, barely awake
    assert circadian_state(3.5)["rest_pressure"] > 0.8  # and a strong pull to rest
    assert circadian_state(15.5)["rest_pressure"] < 0.1


def test_chronotype_is_stable_and_varies_between_residents():
    a = chronotype("saoirse_quinn")
    assert a == chronotype("saoirse_quinn")  # deterministic — a stable trait
    assert abs(a) <= CHRONOTYPE_SPREAD_HOURS
    # Different people land in different places (lark vs owl exists in the pool).
    spread = {chronotype(n) for n in ("ana", "ben", "cy", "dee", "eli", "fox", "gus", "hana")}
    assert max(spread) > 0.5 and min(spread) < -0.5


def test_owl_is_more_awake_after_midnight_than_a_lark():
    owl = circadian_state(1.0, chronotype=CHRONOTYPE_SPREAD_HOURS)["wakefulness"]
    lark = circadian_state(1.0, chronotype=-CHRONOTYPE_SPREAD_HOURS)["wakefulness"]
    assert owl > lark  # at 1am the night owl is still more awake


def test_explicit_chronotype_overrides_and_clamps():
    assert chronotype("whoever", explicit=99.0) == CHRONOTYPE_SPREAD_HOURS
    assert chronotype("whoever", explicit=-1.5) == -1.5


# --- the lever: night quiets the rhythm and opens settling ----------------


def _quiet_producer(*, traces, stimulus, arousal, mode="react"):
    return Pulse.from_dict({"felt_sense": "noted"})


def test_same_stimulus_ignites_by_day_but_not_deep_night(tmp_path_factory):
    day = tmp_path_factory.mktemp("day")
    night = tmp_path_factory.mktemp("night")
    for d, react in ((day, 1.0), (night, circadian_state(3.5)["wakefulness"])):
        _seed_danger(d, 0.9)
        observe_surprise(d, now=T0.isoformat())
        observe_surprise(d, now=(T0 + timedelta(seconds=1)).isoformat())
        r = asyncio.run(tick(d, pulse_producer=_quiet_producer, reactivity=react, now=(T0 + timedelta(seconds=2)).isoformat()))
        globals()[f"_fired_{int(react*100)}"] = r["ignited"]
    assert globals()["_fired_100"] is True  # by day, the danger wakes them
    night_react = int(circadian_state(3.5)["wakefulness"] * 100)
    assert globals()[f"_fired_{night_react}"] is False  # at 3:30am the same input doesn't


def test_night_lets_a_mildly_aroused_resident_settle(tmp_path):
    # A lingering arousal that by day sits above the repose ceiling...
    record_ignition(tmp_path, now=T0.isoformat())
    _seed_danger(tmp_path, 0.6)
    observe_surprise(tmp_path, now=(T0 + timedelta(seconds=400)).isoformat())
    day = check_settling(tmp_path, now=(T0 + timedelta(seconds=400)).isoformat(), reactivity=1.0)
    night = check_settling(tmp_path, now=(T0 + timedelta(seconds=400)).isoformat(), reactivity=circadian_state(3.5)["wakefulness"])
    assert day["settle"] is False  # by day, still too keyed up to settle
    assert night["settle"] is True  # at night the same arousal drops below the ceiling → rest/potter
