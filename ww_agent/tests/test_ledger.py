from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from time import perf_counter

import pytest

from src.runtime import ledger
from src.runtime.salience import derive_arousal, derive_grief, derive_vital
from src.runtime.substrate import derive_afterimage, derive_baseline


def test_cold_ledger_retains_first_event_beyond_old_window(tmp_path) -> None:
    events = [
        {
            "event_id": f"evt-{ordinal}",
            "sequence": ordinal + 1,
            "ts": "2026-07-17T00:00:00+00:00",
            "event_type": "first" if ordinal == 0 else "later",
            "payload": {"ordinal": ordinal},
        }
        for ordinal in range(10_051)
    ]
    first = events[0]
    (tmp_path / "runtime_ledger.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
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


def test_full_replay_uses_only_its_events_and_explicit_as_of(monkeypatch) -> None:
    events = [
        {
            "event_id": "evt-1",
            "sequence": 1,
            "ts": "2026-07-17T12:00:00+00:00",
            "event_type": "research_queued",
            "payload": {"query": "river stones"},
        }
    ]
    first = ledger.reduce_runtime_events(events)

    def reject_wall_clock() -> str:
        raise AssertionError("replay must not read the host wall clock")

    monkeypatch.setattr(ledger, "_utc_now_iso", reject_wall_clock)
    second = ledger.reduce_runtime_events(events)
    later = ledger.reduce_runtime_events(events, as_of="2026-07-18T09:30:00+00:00")

    assert first == second
    assert first.runtime_projection["updated_at"] == events[-1]["ts"]
    assert later.runtime_projection["updated_at"] == "2026-07-18T09:30:00+00:00"
    assert later.subjective_projection["updated_at"] == "2026-07-18T09:30:00+00:00"
    assert later.memory_projection["updated_at"] == "2026-07-18T09:30:00+00:00"
    assert later.subjective_facts["updated_at"] == "2026-07-18T09:30:00+00:00"
    assert later.cognitive_projection["updated_at"] == "2026-07-18T09:30:00+00:00"


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
        "last_sequence": 1,
        "last_event_id": event["event_id"],
    }
    assert checkpoint["state"]["research_queue"][0]["query"] == "harbor light"
    assert not list(tmp_path.glob(".*.tmp"))


def test_new_events_have_monotonic_sequences(tmp_path) -> None:
    first = ledger.append_runtime_event(tmp_path, event_type="first", payload={})
    second = ledger.append_runtime_event(tmp_path, event_type="second", payload={})

    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert ledger.load_runtime_checkpoint(tmp_path)["ledger"]["last_sequence"] == 2


def test_append_accepts_an_authoritative_runtime_timestamp(tmp_path) -> None:
    appended = ledger.append_runtime_event(
        tmp_path,
        event_type="sample",
        payload={},
        ts="2026-07-17T08:15:00-04:00",
    )

    assert appended["ts"] == "2026-07-17T12:15:00+00:00"
    checkpoint = ledger.load_runtime_checkpoint(tmp_path)
    assert checkpoint["state"]["runtime_projection"]["updated_at"] == appended["ts"]


def test_append_migrates_legacy_record_order_without_rewriting_history(
    tmp_path,
) -> None:
    legacy = [
        {
            "event_id": f"evt-legacy-{ordinal}",
            "ts": f"2026-07-17T00:00:0{ordinal}+00:00",
            "event_type": "legacy",
            "payload": {"ordinal": ordinal},
        }
        for ordinal in range(2)
    ]
    ledger_path = tmp_path / "runtime_ledger.jsonl"
    original = "".join(json.dumps(event) + "\n" for event in legacy).encode()
    ledger_path.write_bytes(original)

    appended = ledger.append_runtime_event(tmp_path, event_type="current", payload={})

    assert appended["sequence"] == 3
    assert ledger_path.read_bytes().startswith(original)
    assert ledger.load_runtime_events(tmp_path)[:2] == legacy
    assert ledger.load_runtime_checkpoint(tmp_path)["ledger"]["last_sequence"] == 3


def test_incomplete_tail_is_quarantined_before_the_next_append(tmp_path) -> None:
    first = ledger.append_runtime_event(tmp_path, event_type="first", payload={})
    ledger_path = tmp_path / "runtime_ledger.jsonl"
    with ledger_path.open("ab") as handle:
        handle.write(b'{"event_id":"evt-interrupted"')

    second = ledger.append_runtime_event(tmp_path, event_type="second", payload={})

    events = ledger.load_runtime_events(tmp_path)
    assert [event["event_id"] for event in events] == [
        first["event_id"],
        second["event_id"],
    ]
    assert [event["sequence"] for event in events] == [1, 2]
    quarantines = list(tmp_path.glob("runtime_ledger.corrupt-tail.*.jsonl"))
    assert len(quarantines) == 1
    assert quarantines[0].read_bytes() == b'{"event_id":"evt-interrupted"'


def test_middle_ledger_corruption_fails_without_changing_history(tmp_path) -> None:
    first = ledger.append_runtime_event(tmp_path, event_type="first", payload={})
    ledger_path = tmp_path / "runtime_ledger.jsonl"
    original = ledger_path.read_bytes()
    ledger_path.write_bytes(original + b"{broken}\n")

    with pytest.raises(ledger.LedgerCorruptionError, match="malformed JSON"):
        ledger.load_runtime_events(tmp_path)
    with pytest.raises(ledger.LedgerCorruptionError, match="malformed JSON"):
        ledger.append_runtime_event(tmp_path, event_type="second", payload={})

    assert ledger_path.read_bytes() == original + b"{broken}\n"
    assert first["sequence"] == 1


def test_concurrent_writers_cannot_reuse_a_sequence(tmp_path) -> None:
    def append(ordinal: int) -> dict:
        return ledger.append_runtime_event(
            tmp_path,
            event_type="sample",
            payload={"ordinal": ordinal},
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        appended = list(pool.map(append, range(12)))

    events = ledger.load_runtime_events(tmp_path)
    assert sorted(event["sequence"] for event in appended) == list(range(1, 13))
    assert [event["sequence"] for event in events] == list(range(1, 13))
    assert ledger.load_runtime_checkpoint(tmp_path)["ledger"]["last_sequence"] == 12


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


def test_terminal_packet_history_cannot_evict_an_older_pending_packet() -> None:
    events = [
        {
            "event_id": "evt-pending",
            "ts": "2026-07-17T00:00:00+00:00",
            "event_type": "packet_emitted",
            "payload": {
                "packet_id": "packet-pending",
                "packet_type": "direct_address",
                "created_at": "2026-07-17T00:00:00+00:00",
                "status": "pending",
            },
        }
    ]
    events.extend(
        {
            "event_id": f"evt-observed-{ordinal}",
            "ts": f"2026-07-17T00:01:{ordinal % 60:02d}+00:00",
            "event_type": "packet_emitted",
            "payload": {
                "packet_id": f"packet-observed-{ordinal}",
                "packet_type": "sample",
                "created_at": f"2026-07-17T00:01:{ordinal % 60:02d}+00:00",
                "status": "observed",
            },
        }
        for ordinal in range(ledger.PACKET_PROJECTION_LIMIT)
    )

    packets = ledger.reduce_runtime_events(events).packets

    assert len(packets) == ledger.PACKET_PROJECTION_LIMIT
    assert any(item["packet_id"] == "packet-pending" for item in packets)
    assert sum(item["status"] == "observed" for item in packets) == 199


def test_terminal_intent_history_cannot_evict_an_older_pending_intent() -> None:
    events = [
        {
            "event_id": "evt-pending",
            "ts": "2026-07-17T00:00:00+00:00",
            "event_type": "intent_staged",
            "payload": {
                "intent_id": "intent-pending",
                "intent_type": "inspect",
                "created_at": "2026-07-17T00:00:00+00:00",
                "priority": 0.9,
                "status": "pending",
            },
        }
    ]
    events.extend(
        {
            "event_id": f"evt-executed-{ordinal}",
            "ts": f"2026-07-17T00:01:{ordinal % 60:02d}+00:00",
            "event_type": "intent_staged",
            "payload": {
                "intent_id": f"intent-executed-{ordinal}",
                "intent_type": "sample",
                "created_at": f"2026-07-17T00:01:{ordinal % 60:02d}+00:00",
                "priority": 0.5,
                "status": "executed",
            },
        }
        for ordinal in range(ledger.INTENT_PROJECTION_LIMIT)
    )

    intents = ledger.reduce_runtime_events(events).intents

    assert len(intents) == ledger.INTENT_PROJECTION_LIMIT
    assert any(item["intent_id"] == "intent-pending" for item in intents)
    assert sum(item["status"] == "executed" for item in intents) == 99


def test_open_lifecycle_state_survives_the_complex_replay_boundary(tmp_path) -> None:
    opened = [
        {
            "event_type": "route_state_changed",
            "payload": {
                "status": "active",
                "destination": "Orchard Kitchen",
                "remaining": ["Bridge"],
            },
        },
        {
            "event_type": "mail_intent_staged",
            "payload": {
                "mail_intent_id": "mail-1",
                "recipient": "Mara",
                "context": "A short note",
                "staged_at": "2026-07-17T00:00:01+00:00",
            },
        },
        {
            "event_type": "research_queued",
            "payload": {
                "query": "alder history",
                "priority": "normal",
                "added_ts": "2026-07-17T00:00:02+00:00",
            },
        },
        {
            "event_type": "packet_emitted",
            "payload": {
                "packet_id": "packet-1",
                "packet_type": "direct_address",
                "created_at": "2026-07-17T00:00:03+00:00",
                "status": "pending",
            },
        },
        {
            "event_type": "intent_staged",
            "payload": {
                "intent_id": "intent-1",
                "intent_type": "inspect",
                "created_at": "2026-07-17T00:00:04+00:00",
                "priority": 0.5,
                "status": "pending",
            },
        },
    ]
    events = [
        {
            "event_id": f"evt-{sequence}",
            "sequence": sequence,
            "ts": f"2026-07-17T00:00:{min(sequence, 59):02d}+00:00",
            "event_type": item["event_type"],
            "payload": item["payload"],
        }
        for sequence, item in enumerate(opened, start=1)
    ]
    for sequence in range(len(events) + 1, 10_007):
        events.append(
            {
                "event_id": f"evt-{sequence}",
                "sequence": sequence,
                "ts": "2026-07-17T01:00:00+00:00",
                "event_type": "neutral",
                "payload": {},
            }
        )
    (tmp_path / "runtime_ledger.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )
    ledger.rebuild_runtime_artifacts(tmp_path)

    ledger.append_runtime_event(
        tmp_path,
        event_type="session_state_observed",
        payload={"source": "session_state"},
    )

    state = ledger.load_runtime_checkpoint(tmp_path)["state"]
    assert state["active_route"]["destination"] == "Orchard Kitchen"
    assert state["active_mail_intents"][0]["mail_intent_id"] == "mail-1"
    assert state["research_queue"][0]["query"] == "alder history"
    assert state["packets"][0]["packet_id"] == "packet-1"
    assert state["intents"][0]["intent_id"] == "intent-1"

    terminal_events = [
        ("route_state_changed", {"status": "cleared"}),
        ("mail_intent_sent", {"mail_intent_id": "mail-1"}),
        ("research_popped", {"query": "alder history"}),
        (
            "packet_status_changed",
            {"packet_id": "packet-1", "status": "observed"},
        ),
        (
            "intent_status_changed",
            {"intent_id": "intent-1", "status": "executed"},
        ),
    ]
    for event_type, payload in terminal_events:
        ledger.append_runtime_event(tmp_path, event_type=event_type, payload=payload)

    state = ledger.load_runtime_checkpoint(tmp_path)["state"]
    assert state["active_route"] is None
    assert state["active_mail_intents"] == []
    assert state["research_queue"] == []
    assert state["packets"][0]["status"] == "observed"
    assert state["intents"][0]["status"] == "executed"


def test_incremental_checkpoint_matches_full_replay_after_random_lifecycle_events(
    tmp_path,
) -> None:
    rng = random.Random(137)
    packet_ids = [f"packet-{index}" for index in range(4)]
    intent_ids = [f"intent-{index}" for index in range(4)]
    mail_ids = [f"mail-{index}" for index in range(3)]
    queries = [f"question {index}" for index in range(3)]
    candidates = [
        (
            "packet_emitted",
            {
                "packet_id": packet_id,
                "packet_type": "sample",
                "created_at": f"2026-07-17T12:00:0{index}+00:00",
                "status": "pending",
            },
        )
        for index, packet_id in enumerate(packet_ids)
    ]
    candidates += [
        (
            "packet_status_changed",
            {"packet_id": packet_id, "status": "observed"},
        )
        for packet_id in packet_ids
    ]
    candidates += [
        (
            "intent_staged",
            {
                "intent_id": intent_id,
                "intent_type": "inspect",
                "created_at": f"2026-07-17T12:01:0{index}+00:00",
                "priority": 0.5,
                "status": "pending",
            },
        )
        for index, intent_id in enumerate(intent_ids)
    ]
    candidates += [
        (
            "intent_status_changed",
            {"intent_id": intent_id, "status": "executed"},
        )
        for intent_id in intent_ids
    ]
    candidates += [
        (
            "mail_intent_staged",
            {
                "mail_intent_id": mail_id,
                "recipient": f"Person {index}",
                "staged_at": f"2026-07-17T12:02:0{index}+00:00",
            },
        )
        for index, mail_id in enumerate(mail_ids)
    ]
    candidates += [
        ("mail_intent_sent", {"mail_intent_id": mail_id}) for mail_id in mail_ids
    ]
    candidates += [
        ("research_queued", {"query": query, "priority": "normal"}) for query in queries
    ]
    candidates += [("research_popped", {"query": query}) for query in queries]
    candidates += [
        (
            "route_state_changed",
            {
                "status": "active",
                "destination": f"Place {index}",
                "remaining": [],
            },
        )
        for index in range(3)
    ]
    candidates += [("route_state_changed", {"status": "cleared"})] * 3
    rng.shuffle(candidates)

    for index, (event_type, payload) in enumerate(candidates):
        ts = f"2026-07-18T12:{index:02d}:00+00:00"
        ledger.append_runtime_event(
            tmp_path,
            event_type=event_type,
            payload=payload,
            ts=ts,
        )
        oracle = ledger.reduce_runtime_events(
            ledger.load_runtime_events(tmp_path), as_of=ts
        )
        current = ledger.load_current_runtime_state(tmp_path)
        assert current.packets == oracle.packets
        assert current.intents == oracle.intents
        assert current.active_route == oracle.active_route
        assert current.active_mail_intents == oracle.active_mail_intents
        assert current.research_queue == oracle.research_queue
        assert current.runtime_projection == oracle.runtime_projection
        assert current.subjective_projection == oracle.subjective_projection
        assert current.memory_projection == oracle.memory_projection
        assert current.subjective_facts == oracle.subjective_facts
        assert current.cognitive_projection == oracle.cognitive_projection


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


def test_current_state_and_queue_readers_use_the_checkpoint(
    tmp_path, monkeypatch
) -> None:
    ledger.append_runtime_event(
        tmp_path,
        event_type="packet_emitted",
        payload={
            "packet_id": "packet-1",
            "packet_type": "sample",
            "created_at": "2026-07-17T12:00:00+00:00",
            "status": "pending",
        },
        ts="2026-07-17T12:00:00+00:00",
    )

    def reject_cold_load(_memory_dir):
        raise AssertionError("current-state reads must not load cold history")

    monkeypatch.setattr(ledger, "_load_events", reject_cold_load)

    current = ledger.load_current_runtime_state(tmp_path)
    assert current.packets[0]["packet_id"] == "packet-1"
    assert ledger.derive_packets(tmp_path) == current.packets
    assert ledger.derive_intents(tmp_path) == []
    assert ledger.derive_active_route(tmp_path) is None
    assert ledger.derive_active_mail_intents(tmp_path) == []
    assert ledger.derive_research_queue(tmp_path) == []


def test_normal_append_writes_only_the_ledger_and_checkpoint(tmp_path) -> None:
    ledger.append_runtime_event(tmp_path, event_type="first", payload={})
    ledger.append_runtime_event(tmp_path, event_type="second", payload={})

    assert {path.name for path in tmp_path.iterdir()} == {
        "runtime_checkpoint.json",
        "runtime_ledger.jsonl",
        "runtime_ledger.lock",
    }


def test_explicit_rebuild_removes_legacy_derived_files(tmp_path) -> None:
    legacy_files = {
        "active_route.json",
        "cognitive_projection.json",
        "memory_projection.json",
        "runtime_projection.json",
        "runtime_snapshot.json",
        "subjective_facts.json",
        "subjective_projection.json",
    }
    for filename in legacy_files:
        (tmp_path / filename).write_text("{}\n", encoding="utf-8")
    intents_dir = tmp_path.parent / "letters" / "intents"
    intents_dir.mkdir(parents=True)
    staged = intents_dir / "intent_old_person.md"
    staged.write_text("old projection\n", encoding="utf-8")

    ledger.rebuild_runtime_artifacts(tmp_path)

    assert not any((tmp_path / filename).exists() for filename in legacy_files)
    assert not staged.exists()
    assert (tmp_path / "runtime_checkpoint.json").is_file()


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
