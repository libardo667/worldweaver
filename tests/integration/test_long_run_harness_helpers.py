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


def test_lane_diagnostic_metrics_empty_turns_returns_defaults() -> None:
    """With no turns, narrator_parse_success_rate defaults to 1.0 and revise rate to 0.0."""
    metrics = long_run_harness._lane_diagnostic_metrics([])
    assert metrics["narrator_parse_success_rate"] == 1.0
    assert metrics["referee_decision_valid_rate"] == 1.0
    assert metrics["narrator_revise_decision_rate"] == 0.0
    assert metrics["narrator_parse_attempts"] == 0
    assert metrics["referee_call_attempts"] == 0


def test_lane_diagnostic_metrics_counts_narrator_parse_success() -> None:
    turn_ok = build_turn_record(turn=1, action_source="choice_button", action_sent="go", narrative="text", request_duration_ms=1.0)
    turn_ok.diagnostics = {"narrator_parse_success": True}

    turn_fail = build_turn_record(turn=2, action_source="choice_button", action_sent="look", narrative="fallback", request_duration_ms=1.0)
    turn_fail.diagnostics = {"narrator_parse_success": False}

    metrics = long_run_harness._lane_diagnostic_metrics([turn_ok, turn_fail])
    assert metrics["narrator_parse_attempts"] == 2
    assert metrics["narrator_parse_success_rate"] == 0.5


def test_lane_diagnostic_metrics_skips_turns_without_narrator_field() -> None:
    """Turns without narrator_parse_success (e.g. initial scene) are excluded from the rate."""
    turn_no_field = build_turn_record(turn=1, action_source="initial_scene", action_sent="", narrative="scene", request_duration_ms=1.0)
    turn_no_field.diagnostics = {"clarity_level": "prepared"}  # no narrator_parse_success

    turn_with_field = build_turn_record(turn=2, action_source="choice_button", action_sent="go", narrative="text", request_duration_ms=1.0)
    turn_with_field.diagnostics = {"narrator_parse_success": True}

    metrics = long_run_harness._lane_diagnostic_metrics([turn_no_field, turn_with_field])
    assert metrics["narrator_parse_attempts"] == 1
    assert metrics["narrator_parse_success_rate"] == 1.0


def test_lane_diagnostic_metrics_counts_referee_decision_validity() -> None:
    turn_valid = build_turn_record(turn=1, action_source="choice_button", action_sent="go", narrative="text", request_duration_ms=1.0)
    turn_valid.diagnostics = {"referee_decision": "ok", "referee_decision_valid": True}

    turn_invalid = build_turn_record(turn=2, action_source="choice_button", action_sent="look", narrative="text", request_duration_ms=1.0)
    turn_invalid.diagnostics = {"referee_decision": "ok", "referee_decision_valid": False}

    metrics = long_run_harness._lane_diagnostic_metrics([turn_valid, turn_invalid])
    assert metrics["referee_call_attempts"] == 2
    assert metrics["referee_decision_valid_rate"] == 0.5


def test_lane_diagnostic_metrics_counts_revise_decisions() -> None:
    turn_ok = build_turn_record(turn=1, action_source="choice_button", action_sent="go", narrative="text", request_duration_ms=1.0)
    turn_ok.diagnostics = {"referee_decision": "ok", "referee_decision_valid": True}

    turn_revise = build_turn_record(turn=2, action_source="choice_button", action_sent="look", narrative="text", request_duration_ms=1.0)
    turn_revise.diagnostics = {"referee_decision": "revise", "referee_decision_valid": True}

    metrics = long_run_harness._lane_diagnostic_metrics([turn_ok, turn_revise])
    assert metrics["referee_call_attempts"] == 2
    assert metrics["narrator_revise_decision_rate"] == 0.5


def test_lane_diagnostic_metrics_skips_skipped_referee() -> None:
    """Turns where referee_decision is 'skipped' or 'disabled_budget' are excluded from referee rate."""
    turn_skipped = build_turn_record(turn=1, action_source="choice_button", action_sent="go", narrative="text", request_duration_ms=1.0)
    turn_skipped.diagnostics = {"referee_decision": "skipped"}

    turn_disabled = build_turn_record(turn=2, action_source="choice_button", action_sent="look", narrative="text", request_duration_ms=1.0)
    turn_disabled.diagnostics = {"referee_decision": "disabled_budget"}

    turn_active = build_turn_record(turn=3, action_source="choice_button", action_sent="wait", narrative="text", request_duration_ms=1.0)
    turn_active.diagnostics = {"referee_decision": "ok", "referee_decision_valid": True}

    metrics = long_run_harness._lane_diagnostic_metrics([turn_skipped, turn_disabled, turn_active])
    assert metrics["referee_call_attempts"] == 1
    assert metrics["referee_decision_valid_rate"] == 1.0


def test_projection_and_clarity_metrics_track_hits_waste_and_distribution() -> None:
    turn_one = build_turn_record(
        turn=1,
        action_source="initial_scene",
        action_sent="",
        narrative="Initial projection-backed scene.",
        request_duration_ms=1.0,
    )
    turn_one.diagnostics = {
        "projection_seeded_narration_enabled": True,
        "projection_seed_used": True,
        "projection_seed_storylet_id": 11,
        "fallback_reason": "none",
        "clarity_level": "prepared",
    }

    turn_two = build_turn_record(
        turn=2,
        action_source="choice_button",
        action_sent="Continue",
        narrative="Fallback scene with no projection seed chosen.",
        request_duration_ms=1.0,
    )
    turn_two.diagnostics = {
        "projection_seeded_narration_enabled": True,
        "projection_seed_used": False,
        "fallback_reason": "no_storylet_selected",
        "clarity_level": "unknown",
    }

    metrics = long_run_harness._projection_and_clarity_metrics([turn_one, turn_two])
    assert metrics["projection_stub_count"] == 1.0
    assert metrics["projection_hit_rate"] == 0.5
    assert metrics["projection_waste_rate"] == 0.5
    assert metrics["projection_veto_rate"] == 0.0
    distribution = metrics["clarity_level_distribution"]
    assert distribution["prepared"] == 1
    assert distribution["unknown"] == 1
