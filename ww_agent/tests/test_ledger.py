from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.runtime import ledger


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
