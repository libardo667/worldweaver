from __future__ import annotations

from playtest_harness import long_run_harness
from tests.integration_harness_helpers import build_turn_record


def test_await_prefetch_exits_immediately_for_stable_status_shape(monkeypatch):
    calls = {"count": 0}

    def fake_request_json(method, url, *, payload=None, timeout=0):
        calls["count"] += 1
        return {"stubs_cached": 1, "expires_in_seconds": 12}

    monkeypatch.setattr(long_run_harness, "_request_json", fake_request_json)
    monkeypatch.setattr(long_run_harness.time, "sleep", lambda _: None)

    waited_ms = long_run_harness._await_prefetch(
        "http://127.0.0.1:8000/api",
        "prefetch-session-1",
        timeout=1.0,
        request_timeout=1.0,
    )

    assert waited_ms >= 0.0
    assert calls["count"] == 1


def test_await_prefetch_supports_legacy_prefetch_complete(monkeypatch):
    calls = {"count": 0}
    statuses = [
        {"prefetch_complete": False},
        {"prefetch_complete": True},
    ]

    def fake_request_json(method, url, *, payload=None, timeout=0):
        calls["count"] += 1
        return statuses.pop(0)

    sleep_calls = {"count": 0}

    def fake_sleep(_seconds):
        sleep_calls["count"] += 1

    monkeypatch.setattr(long_run_harness, "_request_json", fake_request_json)
    monkeypatch.setattr(long_run_harness.time, "sleep", fake_sleep)

    waited_ms = long_run_harness._await_prefetch(
        "http://127.0.0.1:8000/api",
        "prefetch-session-2",
        timeout=2.0,
        request_timeout=1.0,
    )

    assert waited_ms >= 0.0
    assert calls["count"] == 2
    assert sleep_calls["count"] == 1


def test_motif_reuse_metrics_detect_repeated_tokens() -> None:
    turn_one = build_turn_record(
        turn=1,
        action_source="initial_scene",
        action_sent="",
        narrative="Neon rain glows over the market while drones sweep alley rooftops.",
        request_duration_ms=1.0,
    )
    turn_two = build_turn_record(
        turn=2,
        action_source="choice_button",
        action_sent="explore",
        narrative="Neon lights cut through rain again as drones crowd the market edge.",
        request_duration_ms=1.0,
    )
    metrics = long_run_harness._motif_reuse_metrics([turn_one, turn_two])
    assert metrics["motif_total_tokens"] > 0.0
    assert metrics["motif_overlap_count"] > 0.0
    assert metrics["motif_reuse_rate"] > 0.0
    assert isinstance(metrics["motif_top_reused"], list)
