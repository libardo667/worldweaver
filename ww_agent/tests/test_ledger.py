from __future__ import annotations

import json

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
