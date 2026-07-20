from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from time import perf_counter

import pytest

from src.runtime import ledger
from src.runtime.salience import derive_arousal, derive_grief, derive_vital
from src.runtime.substrate import derive_afterimage, derive_baseline


def test_cold_ledger_retains_first_event_beyond_old_window(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(ledger, "rebuild_runtime_artifacts", lambda _memory_dir: None)
    first = ledger.append_runtime_event(
        tmp_path, event_type="first", payload={"ordinal": 0}
    )

    for ordinal in range(1, 10_051):
        ledger.append_runtime_event(
            tmp_path, event_type="later", payload={"ordinal": ordinal}
        )

    events = ledger.load_runtime_events(tmp_path)
    assert len(events) == 10_051
    assert events[0] == first
    assert events[-1]["payload"]["ordinal"] == 10_050

    raw_lines = (
        (tmp_path / "runtime_ledger.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(raw_lines) == 10_051
    assert json.loads(raw_lines[0]) == first


def test_runtime_reducer_read_uses_bounded_tail(tmp_path) -> None:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    path = tmp_path / "runtime_ledger.jsonl"
    events = [
        {
            "event_id": f"evt-{ordinal}",
            "ts": (start + timedelta(hours=ordinal)).isoformat(),
            "event_type": "sample",
            "payload": {"ordinal": ordinal},
        }
        for ordinal in range(100)
    ]
    path.write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )

    hot = ledger.load_runtime_reducer_events(tmp_path)

    assert hot[0]["payload"]["ordinal"] == 75
    assert hot[-1]["payload"]["ordinal"] == 99
    assert ledger.load_runtime_events(tmp_path)[0]["payload"]["ordinal"] == 0


def test_runtime_reducer_window_cannot_undercut_longest_timescale(tmp_path) -> None:
    with pytest.raises(ValueError, match="longest reducer half-life"):
        ledger.load_runtime_reducer_events(
            tmp_path,
            window_seconds=ledger.LONGEST_RUNTIME_REDUCER_HALF_LIFE_SECONDS - 1,
        )


def test_projection_replay_reads_only_requested_recent_events(tmp_path) -> None:
    path = tmp_path / "runtime_ledger.jsonl"
    events = [
        {
            "event_id": f"evt-{ordinal}",
            "ts": f"2026-07-17T00:00:{ordinal:02d}+00:00",
            "event_type": "sample",
            "payload": {"ordinal": ordinal},
        }
        for ordinal in range(12)
    ]
    path.write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )

    recent = ledger.load_runtime_projection_events(tmp_path, max_events=5)

    assert [item["payload"]["ordinal"] for item in recent] == [7, 8, 9, 10, 11]
    assert ledger.load_runtime_events(tmp_path)[0]["payload"]["ordinal"] == 0


def test_hot_reducer_window_matches_cold_history_on_frozen_ledger(tmp_path) -> None:
    now = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)

    def event(
        event_id: str, seconds_ago: float, event_type: str, payload: dict
    ) -> dict:
        ts = (now - timedelta(seconds=seconds_ago)).isoformat()
        return {
            "event_id": event_id,
            "ts": ts,
            "event_type": event_type,
            "payload": payload,
        }

    events = [
        event("old", 3 * 86400, "unrelated", {}),
        event(
            "present",
            600,
            "surprise_observed",
            {
                "observed_ts": (now - timedelta(seconds=600)).isoformat(),
                "magnitude": 0.2,
                "anchor_present": ["hearth"],
            },
        ),
        event(
            "ignition",
            400,
            "ignition_fired",
            {"fired_ts": (now - timedelta(seconds=400)).isoformat()},
        ),
        event(
            "absence",
            300,
            "surprise_observed",
            {
                "observed_ts": (now - timedelta(seconds=300)).isoformat(),
                "magnitude": 0.3,
                "grief_field": [{"tag": "hearth", "predicted": 0.8}],
            },
        ),
        event(
            "baseline",
            120,
            "baseline_updated",
            {
                "updated_ts": (now - timedelta(seconds=120)).isoformat(),
                "by_scope": {"self": {"curiosity": 0.7}},
            },
        ),
        event(
            "afterimage",
            60,
            "afterimage_cast",
            {
                "cast_ts": (now - timedelta(seconds=60)).isoformat(),
                "scope": "self",
                "confidence": 0.9,
                "half_life": 600,
                "features": {"social_pull": 0.6},
            },
        ),
    ]
    (tmp_path / "runtime_ledger.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in events), encoding="utf-8"
    )
    cold = ledger.load_runtime_events(tmp_path)
    hot = ledger.load_runtime_reducer_events(tmp_path, now=now)

    assert derive_grief(hot, now=now) == derive_grief(cold, now=now)
    assert derive_arousal(hot, now=now) == derive_arousal(cold, now=now)
    assert derive_vital(hot, now=now) == derive_vital(cold, now=now)
    assert derive_baseline(hot, now=now) == derive_baseline(cold, now=now)
    assert derive_afterimage(hot, now=now) == derive_afterimage(cold, now=now)


def test_rebuild_writes_versioned_current_checkpoint_atomically(tmp_path) -> None:
    event = ledger.append_runtime_event(
        tmp_path,
        event_type="research_queued",
        payload={"query": "harbor light", "priority": "high"},
    )

    checkpoint = ledger.load_runtime_checkpoint(tmp_path)

    assert checkpoint is not None
    assert checkpoint["format_version"] == ledger.CHECKPOINT_FORMAT_VERSION
    assert checkpoint["reducer_version"] == ledger.REDUCER_FORMAT_VERSION
    assert checkpoint["projection_versions"] == ledger.PROJECTION_FORMAT_VERSIONS
    assert checkpoint["ledger"] == {
        "byte_offset": (tmp_path / "runtime_ledger.jsonl").stat().st_size,
        "event_count": 1,
        "last_event_id": event["event_id"],
    }
    assert checkpoint["state"]["research_queue"][0]["query"] == "harbor light"
    assert not list(tmp_path.glob(".*.tmp"))


def test_checkpoint_requires_exact_cold_ledger_offset_and_known_versions(
    tmp_path,
) -> None:
    ledger.append_runtime_event(tmp_path, event_type="first", payload={})
    checkpoint_path = tmp_path / "runtime_checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    ledger._append_event(
        tmp_path,
        {
            "event_id": "evt-uncheckpointed",
            "ts": "2026-07-17T00:00:00+00:00",
            "event_type": "second",
            "payload": {},
        },
    )

    assert ledger.load_runtime_checkpoint(tmp_path) is None
    assert ledger.load_runtime_checkpoint(tmp_path, require_current=False) is not None

    checkpoint["format_version"] += 1
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    assert ledger.load_runtime_checkpoint(tmp_path, require_current=False) is None


def test_append_recovers_a_corrupt_checkpoint_from_complete_history(
    tmp_path, monkeypatch
) -> None:
    fixed_now = "2026-07-17T12:00:00+00:00"
    monkeypatch.setattr(ledger, "_utc_now_iso", lambda: fixed_now)
    ledger.append_runtime_event(tmp_path, event_type="first", payload={})
    (tmp_path / "runtime_checkpoint.json").write_text("{broken", encoding="utf-8")

    appended = ledger.append_runtime_event(
        tmp_path,
        event_type="movement_arrived",
        payload={"destination": "North Beach", "arrived_at": fixed_now},
    )

    checkpoint = ledger.load_runtime_checkpoint(tmp_path)
    assert checkpoint is not None
    assert checkpoint["ledger"]["event_count"] == 2
    assert checkpoint["ledger"]["last_event_id"] == appended["event_id"]
    oracle = ledger.reduce_runtime_events(ledger.load_runtime_events(tmp_path))
    state = checkpoint["state"]
    assert state["runtime_projection"] == oracle.runtime_projection
    assert state["subjective_projection"] == oracle.subjective_projection
    assert state["memory_projection"] == oracle.memory_projection
    assert state["subjective_facts"] == oracle.subjective_facts
    assert state["cognitive_projection"] == oracle.cognitive_projection


def test_operational_queue_projections_are_bounded_without_truncating_cold_events() -> (
    None
):
    events = [
        {
            "event_id": f"evt-{ordinal}",
            "ts": f"2026-07-17T00:{ordinal // 60:02d}:{ordinal % 60:02d}+00:00",
            "event_type": "packet_emitted",
            "payload": {
                "packet_id": f"packet-{ordinal}",
                "packet_type": "sample",
                "created_at": f"2026-07-17T00:{ordinal // 60:02d}:{ordinal % 60:02d}+00:00",
                "status": "observed",
            },
        }
        for ordinal in range(250)
    ]

    reduced = ledger.reduce_runtime_events(events)

    assert len(reduced.events) == 250
    assert len(reduced.packets) == ledger.PACKET_PROJECTION_LIMIT
    assert reduced.packets[0]["packet_id"] == "packet-50"
    assert reduced.packets[-1]["packet_id"] == "packet-249"


def test_projection_neutral_append_advances_checkpoint_without_loading_cold_history(
    tmp_path, monkeypatch
) -> None:
    fixed_now = "2026-07-17T12:00:00+00:00"
    monkeypatch.setattr(ledger, "_utc_now_iso", lambda: fixed_now)
    ledger.append_runtime_event(
        tmp_path, event_type="research_queued", payload={"query": "tidal archive"}
    )
    original_load = ledger._load_events

    def reject_cold_load(_memory_dir):
        raise AssertionError("projection-neutral append must not load cold history")

    monkeypatch.setattr(ledger, "_load_events", reject_cold_load)
    appended = ledger.append_runtime_event(
        tmp_path,
        event_type="afterimage_cast",
        payload={"scope": "self", "features": {"curiosity": 0.6}, "half_life": 600},
    )

    checkpoint = ledger.load_runtime_checkpoint(tmp_path)
    assert checkpoint is not None
    assert checkpoint["ledger"]["event_count"] == 2
    assert checkpoint["ledger"]["last_event_id"] == appended["event_id"]
    assert checkpoint["state"]["runtime_projection"]["event_counts"] == {
        "research_queued": 1,
        "afterimage_cast": 1,
    }

    cold = original_load(tmp_path)
    oracle = ledger.reduce_runtime_events(cold)
    state = checkpoint["state"]
    assert state["packets"] == oracle.packets
    assert state["intents"] == oracle.intents
    assert state["research_queue"] == oracle.research_queue
    assert state["runtime_projection"] == oracle.runtime_projection
    assert state["subjective_projection"] == oracle.subjective_projection
    assert state["memory_projection"] == oracle.memory_projection
    assert state["subjective_facts"] == oracle.subjective_facts
    assert state["cognitive_projection"] == oracle.cognitive_projection


def test_simple_queue_updates_advance_checkpoint_without_loading_cold_history(
    tmp_path, monkeypatch
) -> None:
    fixed_now = "2026-07-17T12:00:00+00:00"
    monkeypatch.setattr(ledger, "_utc_now_iso", lambda: fixed_now)
    ledger.append_runtime_event(
        tmp_path,
        event_type="packet_emitted",
        payload={
            "packet_id": "packet-1",
            "packet_type": "sample",
            "created_at": fixed_now,
            "status": "pending",
        },
    )
    original_load = ledger._load_events

    def reject_cold_load(_memory_dir):
        raise AssertionError("simple queue updates must not load cold history")

    monkeypatch.setattr(ledger, "_load_events", reject_cold_load)
    ledger.append_runtime_event(
        tmp_path,
        event_type="packet_status_changed",
        payload={"packet_id": "packet-1", "status": "observed"},
    )
    ledger.append_runtime_event(
        tmp_path,
        event_type="intent_staged",
        payload={
            "intent_id": "intent-1",
            "intent_type": "inspect",
            "created_at": fixed_now,
            "priority": 0.8,
            "status": "pending",
        },
    )
    ledger.append_runtime_event(
        tmp_path,
        event_type="intent_status_changed",
        payload={
            "intent_id": "intent-1",
            "status": "executed",
            "validation_state": "valid",
        },
    )

    checkpoint = ledger.load_runtime_checkpoint(tmp_path)
    assert checkpoint is not None
    cold = original_load(tmp_path)
    oracle = ledger.reduce_runtime_events(cold)
    state = checkpoint["state"]
    assert state["packets"] == oracle.packets
    assert state["intents"] == oracle.intents
    assert state["runtime_projection"] == oracle.runtime_projection
    assert state["subjective_projection"] == oracle.subjective_projection
    assert state["memory_projection"] == oracle.memory_projection
    assert state["subjective_facts"] == oracle.subjective_facts
    assert state["cognitive_projection"] == oracle.cognitive_projection


def test_complex_update_replays_bounded_history_without_loading_cold_history(
    tmp_path, monkeypatch
) -> None:
    fixed_now = "2026-07-17T12:00:00+00:00"
    monkeypatch.setattr(ledger, "_utc_now_iso", lambda: fixed_now)
    ledger.append_runtime_event(tmp_path, event_type="first", payload={})
    original_load = ledger._load_events

    def reject_cold_load(_memory_dir):
        raise AssertionError("normal complex updates must not load cold history")

    monkeypatch.setattr(ledger, "_load_events", reject_cold_load)
    ledger.append_runtime_event(
        tmp_path,
        event_type="movement_blocked",
        payload={"destination": "North Beach", "status": "blocked"},
    )

    checkpoint = ledger.load_runtime_checkpoint(tmp_path)
    assert checkpoint is not None
    cold = original_load(tmp_path)
    oracle = ledger.reduce_runtime_events(cold)
    state = checkpoint["state"]
    assert state["runtime_projection"] == oracle.runtime_projection
    assert state["subjective_projection"] == oracle.subjective_projection
    assert state["memory_projection"] == oracle.memory_projection
    assert state["subjective_facts"] == oracle.subjective_facts
    assert state["cognitive_projection"] == oracle.cognitive_projection


def test_complex_update_cost_stays_flat_at_one_hundred_thousand_events(
    tmp_path,
) -> None:
    seed_event = {
        "event_id": "evt-seed",
        "ts": "2026-07-17T12:00:00+00:00",
        "event_type": "sample",
        "payload": {},
    }
    encoded = json.dumps(seed_event) + "\n"
    replay_events = [seed_event] * ledger.PROJECTION_REPLAY_MAX_EVENTS
    replayed = ledger.reduce_runtime_events(replay_events)

    def seed(memory_dir, event_count: int) -> None:
        memory_dir.mkdir(parents=True)
        (memory_dir / "runtime_ledger.jsonl").write_text(
            encoded * event_count, encoding="utf-8"
        )
        runtime_projection = dict(replayed.runtime_projection)
        runtime_projection["ledger_event_count"] = event_count
        runtime_projection["event_counts"] = {"sample": event_count}
        seeded = replace(replayed, runtime_projection=runtime_projection)
        ledger._write_reduced_runtime_artifacts(memory_dir, seeded)

    small = tmp_path / "ten_thousand"
    large = tmp_path / "one_hundred_thousand"
    seed(small, 10_000)
    seed(large, 100_000)

    def timed_update(memory_dir) -> float:
        started = perf_counter()
        ledger.append_runtime_event(
            memory_dir,
            event_type="action_executed",
            payload={"action": "look around", "location": "North Beach"},
        )
        return perf_counter() - started

    small_seconds = timed_update(small)
    large_seconds = timed_update(large)

    assert ledger.load_runtime_checkpoint(large)["ledger"]["event_count"] == 100_001
    assert large_seconds <= (small_seconds * 2.0) + 0.05
