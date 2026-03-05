"""Integration tests for same-session concurrent request safety."""

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time
from unittest.mock import patch

from src.services.command_interpreter import ActionResult


def test_same_session_next_and_action_do_not_overlap_critical_section(seeded_client):
    session_id = "concurrent-phase-order"
    event_log: list[tuple[str, str, float]] = []
    event_lock = Lock()

    def _record(endpoint: str, marker: str):
        with event_lock:
            event_log.append((endpoint, marker, time.perf_counter()))

    def _fake_next(*args, **kwargs):
        _record("next", "start")
        time.sleep(0.12)
        _record("next", "end")
        return {
            "response": {
                "text": "Serialized next.",
                "choices": [{"label": "Continue", "set": {}}],
                "vars": {},
            },
            "debug": None,
        }

    def _fake_action(*args, **kwargs):
        _record("action", "start")
        time.sleep(0.12)
        _record("action", "end")
        return {
            "narrative": "Serialized action.",
            "state_changes": {},
            "choices": [{"label": "Continue", "set": {}}],
            "plausible": True,
            "vars": {},
        }

    with (
        patch("src.services.turn_service.TurnOrchestrator.process_next_turn", side_effect=_fake_next),
        patch("src.services.turn_service.TurnOrchestrator.process_action_turn", side_effect=_fake_action),
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_next = pool.submit(
                seeded_client.post,
                "/api/next",
                json={"session_id": session_id, "vars": {}},
            )
            fut_action = pool.submit(
                seeded_client.post,
                "/api/action",
                json={"session_id": session_id, "action": "inspect"},
            )
            next_response = fut_next.result(timeout=5)
            action_response = fut_action.result(timeout=5)

    assert next_response.status_code == 200
    assert action_response.status_code == 200
    ordered = [entry[:2] for entry in sorted(event_log, key=lambda item: item[2])]
    assert ordered in (
        [("next", "start"), ("next", "end"), ("action", "start"), ("action", "end")],
        [("action", "start"), ("action", "end"), ("next", "start"), ("next", "end")],
    )


def test_concurrent_next_and_action_preserve_combined_state(seeded_client):
    session_id = "concurrent-state-persistence"
    seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})

    action_result = ActionResult(
        narrative_text="You inspect the brazier and mark the chamber.",
        state_deltas={"action_marker": True},
        should_trigger_storylet=False,
        follow_up_choices=[{"label": "Continue", "set": {}}],
        plausible=True,
    )

    with patch("src.services.command_interpreter.interpret_action", return_value=action_result):
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_next = pool.submit(
                seeded_client.post,
                "/api/next",
                json={"session_id": session_id, "vars": {"next_marker": 7}},
            )
            fut_action = pool.submit(
                seeded_client.post,
                "/api/action",
                json={"session_id": session_id, "action": "I inspect the brazier"},
            )
            next_response = fut_next.result(timeout=5)
            action_response = fut_action.result(timeout=5)

    assert next_response.status_code == 200
    assert action_response.status_code == 200
    state = seeded_client.get(f"/api/state/{session_id}").json()["variables"]
    assert state.get("next_marker") == 7
    assert state.get("action_marker") is True
