from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.runtime.ledger import load_runtime_events, rebuild_runtime_artifacts, reduce_runtime_events
from src.runtime.pulse import (
    Pulse,
    PulseValidationError,
    SelfDelta,
    constitution_gate,
    route_pulse,
)
from src.runtime.substrate import active_drive_nudges, derive_afterimage, predict


def _events_by_type(memory_dir, event_type):
    return [event for event in load_runtime_events(memory_dir) if str(event.get("event_type") or "").strip() == event_type]


# --- validation -----------------------------------------------------------


def test_pulse_validates_and_clamps_typed_contract():
    pulse = Pulse.from_dict(
        {
            "felt_sense": "  a slow warmth settling  ",
            "act": {"kind": "Speak", "body": "Hello there.", "target": "Levi"},
            "expectations": [
                {"features": {"warmth": 1.7, "noise": -0.4, "": 0.5}, "scope": "self", "confidence": 2.0, "half_life": 300},
            ],
            "drive_nudges": [{"features": {"curiosity": 0.6}, "half_life": 0}],
            "self_delta": {"new_reverie": "the fog feels like company"},
            "trace_verdicts": [{"trace_id": "tr-1", "verdict": "Consolidate"}],
        }
    )

    assert pulse.felt_sense == "a slow warmth settling"
    assert pulse.act is not None and pulse.act.kind == "speak" and pulse.act.target == "Levi"
    exp = pulse.expectations[0]
    assert exp.features == {"warmth": 1.0}  # clamped to 1, negative + unnamed dropped
    assert exp.scope == "self" and exp.confidence == 1.0
    # half_life of 0 falls back to the drive-nudge default rather than staying 0.
    assert pulse.drive_nudges[0].half_life > 0.0
    assert pulse.trace_verdicts[0].verdict == "consolidate"


def test_pulse_rejects_invalid_act_strictly():
    # act is the only path to the world, so a malformed act fails the whole pulse.
    with pytest.raises(PulseValidationError):
        Pulse.from_dict({"act": {"kind": "teleport", "body": "x"}})
    with pytest.raises(PulseValidationError):
        Pulse.from_dict({"act": {"kind": "speak", "body": ""}})


def test_soft_fields_degrade_gracefully():
    # A malformed inner item is dropped, never failing an otherwise-good pulse —
    # the act survives. (Observed against the real model emitting empty nudges.)
    pulse = Pulse.from_dict(
        {
            "act": {"kind": "speak", "body": "Jasmine, Levi?"},
            "expectations": [{"features": {}}, {"features": {"social_pull": 0.8}, "scope": "self"}],
            "drive_nudges": [{"features": {}}],
            "trace_verdicts": [{"trace_id": "t", "verdict": "ignore"}, {"trace_id": "ok", "verdict": "watch"}],
        }
    )
    assert pulse.act is not None and pulse.act.body == "Jasmine, Levi?"
    assert [e.features for e in pulse.expectations] == [{"social_pull": 0.8}]  # empty one dropped
    assert pulse.drive_nudges == []  # empty nudge dropped, not fatal
    assert [(t.trace_id, t.verdict) for t in pulse.trace_verdicts] == [("ok", "watch")]  # bad verdict dropped


def test_empty_pulse_is_valid():
    pulse = Pulse.from_dict({})
    assert pulse.act is None
    assert pulse.expectations == []
    assert pulse.self_delta.is_empty()


# --- routing: felt_sense is a readout, act is the only world path ----------


def test_felt_sense_is_logged_not_routed_as_control(tmp_path):
    pulse = Pulse.from_dict({"felt_sense": "the room has gone quiet"})
    route_pulse(tmp_path, pulse)

    logged = _events_by_type(tmp_path, "felt_sense_logged")
    assert len(logged) == 1
    assert logged[0]["payload"]["felt_sense"] == "the room has gone quiet"

    # felt_sense alone produces no world act and no prediction.
    assert _events_by_type(tmp_path, "pulse_act_emitted") == []
    assert predict(tmp_path)["by_scope"] == {}


def test_act_is_the_only_path_to_the_world(tmp_path):
    route_pulse(tmp_path, Pulse.from_dict({"felt_sense": "no move"}))
    assert _events_by_type(tmp_path, "pulse_act_emitted") == []

    route_pulse(tmp_path, Pulse.from_dict({"act": {"kind": "move", "body": "head to North Beach", "target": "North Beach"}}))
    acts = _events_by_type(tmp_path, "pulse_act_emitted")
    assert len(acts) == 1
    assert acts[0]["payload"]["kind"] == "move"
    assert acts[0]["payload"]["target"] == "North Beach"


# --- afterimage: decaying top-down prediction -----------------------------


def test_expectations_become_decaying_afterimage(tmp_path):
    t0 = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)
    pulse = Pulse.from_dict(
        {
            "expectations": [
                {"features": {"warmth": 0.8}, "scope": "here", "confidence": 1.0, "half_life": 600},
            ]
        }
    )
    route_pulse(tmp_path, pulse, now=t0.isoformat())

    # Immediately after casting, the prediction is near full strength.
    fresh = predict(tmp_path, now=t0.isoformat())
    assert fresh["by_scope"]["here"]["warmth"] == pytest.approx(0.8, abs=1e-3)

    # One half-life later it has decayed by half.
    half = predict(tmp_path, now=(t0 + timedelta(seconds=600)).isoformat())
    assert half["by_scope"]["here"]["warmth"] == pytest.approx(0.4, abs=1e-3)

    # Many half-lives later it has faded below epsilon and drops out entirely.
    gone = predict(tmp_path, now=(t0 + timedelta(seconds=6000)).isoformat())
    assert gone["by_scope"] == {}


def test_afterimage_aggregates_by_scope_with_freshest_winning(tmp_path):
    t0 = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)
    route_pulse(
        tmp_path,
        Pulse.from_dict({"expectations": [{"features": {"calm": 0.9}, "scope": "self", "half_life": 600, "confidence": 1.0}]}),
        now=t0.isoformat(),
    )
    # An older, weaker cast for the same scope/tag is dominated by the fresh one.
    route_pulse(
        tmp_path,
        Pulse.from_dict({"expectations": [{"features": {"calm": 0.3}, "scope": "self", "half_life": 600, "confidence": 1.0}]}),
        now=(t0 - timedelta(seconds=1200)).isoformat(),
    )
    field = predict(tmp_path, now=t0.isoformat())
    assert field["by_scope"]["self"]["calm"] == pytest.approx(0.9, abs=1e-3)


def test_drive_nudges_decay_independently(tmp_path):
    t0 = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)
    route_pulse(
        tmp_path,
        Pulse.from_dict({"drive_nudges": [{"features": {"curiosity": 0.6}, "half_life": 300}]}),
        now=t0.isoformat(),
    )
    fresh = active_drive_nudges(tmp_path, now=t0.isoformat())
    assert fresh["by_scope"]["here"]["curiosity"] == pytest.approx(0.6, abs=1e-3)
    half = active_drive_nudges(tmp_path, now=(t0 + timedelta(seconds=300)).isoformat())
    assert half["by_scope"]["here"]["curiosity"] == pytest.approx(0.3, abs=1e-3)
    # Drive nudges do not leak into the afterimage prediction.
    assert predict(tmp_path, now=t0.isoformat())["by_scope"] == {}


def test_afterimage_is_ledger_derived_single_source(tmp_path):
    t0 = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)
    route_pulse(
        tmp_path,
        Pulse.from_dict({"expectations": [{"features": {"warmth": 0.5}, "scope": "here", "half_life": 600, "confidence": 1.0}]}),
        now=t0.isoformat(),
    )
    # Re-deriving straight from a fresh ledger read matches predict(): no
    # second source of truth, nothing cached.
    from_events = derive_afterimage(load_runtime_events(tmp_path), now=t0.isoformat())
    assert from_events == predict(tmp_path, now=t0.isoformat())


# --- self_delta: the constitution gate ------------------------------------


def test_self_delta_passes_gate_and_never_writes_canonical(tmp_path):
    canonical = tmp_path / "identity" / "SOUL.canonical.md"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("I am steady. I do not abandon my people.\n", encoding="utf-8")
    before = canonical.read_text(encoding="utf-8")

    route_pulse(
        tmp_path,
        Pulse.from_dict({"self_delta": {"soul_edit": "I have grown more patient", "goal_update": "find the tea house"}}),
    )

    staged = _events_by_type(tmp_path, "self_delta_staged")
    assert {item["payload"]["kind"] for item in staged} == {"soul_edit", "goal_update"}
    assert all(item["payload"]["verdict"] == "accepted" for item in staged)
    # The hard invariant: routing never touches canonical identity.
    assert canonical.read_text(encoding="utf-8") == before


def test_constitution_gate_drops_contradicting_edit():
    def check(kind, body):
        return "drop" if "abandon" in body else None

    decisions = constitution_gate(
        SelfDelta(soul_edit="I will abandon my people", new_reverie="the fog is kind"),
        contradiction_check=check,
    )
    by_kind = {decision.kind: decision for decision in decisions}
    assert by_kind["soul_edit"].verdict == "dropped"
    assert by_kind["soul_edit"].reason == "contradicts_immutable_direction"
    assert by_kind["new_reverie"].verdict == "accepted"


def test_gate_contradiction_check_routes_through_route_pulse(tmp_path):
    route_pulse(
        tmp_path,
        Pulse.from_dict({"self_delta": {"soul_edit": "I will abandon my post"}}),
        gate_contradiction_check=lambda kind, body: "drop" if "abandon" in body else None,
    )
    staged = _events_by_type(tmp_path, "self_delta_staged")
    assert len(staged) == 1
    assert staged[0]["payload"]["verdict"] == "dropped"


# --- trace verdicts + provenance ------------------------------------------


def test_trace_verdicts_are_recorded(tmp_path):
    route_pulse(
        tmp_path,
        Pulse.from_dict({"trace_verdicts": [{"trace_id": "tr-a", "verdict": "consolidate"}, {"trace_id": "tr-b", "verdict": "release"}]}),
    )
    recorded = _events_by_type(tmp_path, "trace_verdict_recorded")
    assert {(item["payload"]["trace_id"], item["payload"]["verdict"]) for item in recorded} == {
        ("tr-a", "consolidate"),
        ("tr-b", "release"),
    }


def test_pulse_emitted_carries_full_provenance(tmp_path):
    raw = {
        "felt_sense": "alert",
        "act": {"kind": "speak", "body": "Who's there?"},
        "expectations": [{"features": {"vigilance": 0.7}, "scope": "here", "half_life": 600, "confidence": 0.9}],
    }
    summary = route_pulse(tmp_path, Pulse.from_dict(raw))

    emitted = _events_by_type(tmp_path, "pulse_emitted")
    assert len(emitted) == 1
    stored = emitted[0]["payload"]["pulse"]
    assert stored["felt_sense"] == "alert"
    assert stored["act"]["body"] == "Who's there?"
    assert stored["expectations"][0]["features"] == {"vigilance": 0.7}
    assert summary["pulse_id"] == emitted[0]["payload"]["pulse_id"]


def test_pulse_events_do_not_disturb_existing_projections(tmp_path):
    # Routing pulses through the canonical ledger leaves the Major 46 reducers
    # intact — new event types are simply ignored by the existing builders.
    route_pulse(tmp_path, Pulse.from_dict({"felt_sense": "x", "expectations": [{"features": {"warmth": 0.5}}]}))
    reduced = reduce_runtime_events(load_runtime_events(tmp_path))
    assert reduced.cognitive_projection["active_nodes"] == []
    # A rebuild stays consistent (no crash, projections still derivable).
    rebuilt = rebuild_runtime_artifacts(tmp_path)
    assert rebuilt.runtime_projection["event_counts"].get("afterimage_cast") == 1
