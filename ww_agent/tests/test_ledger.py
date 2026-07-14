from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.runtime import ledger
from src.runtime.salience import derive_arousal, derive_grief, derive_vital
from src.runtime.substrate import derive_afterimage, derive_baseline


def test_cold_ledger_retains_first_event_beyond_old_window(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ledger, "rebuild_runtime_artifacts", lambda _memory_dir: None)
    first = ledger.append_runtime_event(tmp_path, event_type="first", payload={"ordinal": 0})

    for ordinal in range(1, 10_051):
        ledger.append_runtime_event(tmp_path, event_type="later", payload={"ordinal": ordinal})

    events = ledger.load_runtime_events(tmp_path)
    assert len(events) == 10_051
    assert events[0] == first
    assert events[-1]["payload"]["ordinal"] == 10_050

    raw_lines = (tmp_path / "runtime_ledger.jsonl").read_text(encoding="utf-8").splitlines()
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
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")

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


def test_hot_reducer_window_matches_cold_history_on_frozen_ledger(tmp_path) -> None:
    now = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)

    def event(event_id: str, seconds_ago: float, event_type: str, payload: dict) -> dict:
        ts = (now - timedelta(seconds=seconds_ago)).isoformat()
        return {"event_id": event_id, "ts": ts, "event_type": event_type, "payload": payload}

    events = [
        event("old", 3 * 86400, "unrelated", {}),
        event("present", 600, "surprise_observed", {"observed_ts": (now - timedelta(seconds=600)).isoformat(), "magnitude": 0.2, "anchor_present": ["hearth"]}),
        event("ignition", 400, "ignition_fired", {"fired_ts": (now - timedelta(seconds=400)).isoformat()}),
        event("absence", 300, "surprise_observed", {"observed_ts": (now - timedelta(seconds=300)).isoformat(), "magnitude": 0.3, "grief_field": [{"tag": "hearth", "predicted": 0.8}]}),
        event("baseline", 120, "baseline_updated", {"updated_ts": (now - timedelta(seconds=120)).isoformat(), "by_scope": {"self": {"curiosity": 0.7}}}),
        event("afterimage", 60, "afterimage_cast", {"cast_ts": (now - timedelta(seconds=60)).isoformat(), "scope": "self", "confidence": 0.9, "half_life": 600, "features": {"social_pull": 0.6}}),
    ]
    (tmp_path / "runtime_ledger.jsonl").write_text("".join(json.dumps(item) + "\n" for item in events), encoding="utf-8")
    cold = ledger.load_runtime_events(tmp_path)
    hot = ledger.load_runtime_reducer_events(tmp_path, now=now)

    assert derive_grief(hot, now=now) == derive_grief(cold, now=now)
    assert derive_arousal(hot, now=now) == derive_arousal(cold, now=now)
    assert derive_vital(hot, now=now) == derive_vital(cold, now=now)
    assert derive_baseline(hot, now=now) == derive_baseline(cold, now=now)
    assert derive_afterimage(hot, now=now) == derive_afterimage(cold, now=now)
