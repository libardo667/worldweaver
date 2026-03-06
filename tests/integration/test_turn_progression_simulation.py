import pytest
from src.models import WorldEvent
from src.services.world_memory import EVENT_TYPE_SIMULATION_TICK
from src.config import settings
from playtest_harness import long_run_harness
from tests.integration_helpers import assert_ok_response


def test_api_action_triggers_simulation_tick(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "enable_simulation_tick", True)
    session_id = "test-sim-integration-1"

    # Establish base state with danger
    from src.services.state_manager import AdvancedStateManager
    from src.services.session_service import save_state, get_state_manager as load_state

    manager = AdvancedStateManager(session_id=session_id)
    manager.set_variable("environment.danger_level", 5.0)
    save_state(manager, db_session)

    # Make a freeform action
    payload = {"session_id": session_id, "action": "I wait patiently."}
    response = client.post("/api/action", json=payload)
    assert_ok_response(response)

    # Verify simulation tick was recorded in world memory
    events = db_session.query(WorldEvent).filter_by(session_id=session_id, event_type=EVENT_TYPE_SIMULATION_TICK).all()

    assert len(events) == 1
    event = events[0]
    assert event.summary == "Deterministic world simulation tick"

    # Check that danger actually went up
    manager = load_state(session_id, db_session)
    new_danger = manager.get_variable("environment.danger_level")
    assert new_danger > 5.0
    assert new_danger == pytest.approx(5.1)


def test_api_next_triggers_simulation_tick(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "enable_simulation_tick", True)
    session_id = "test-sim-integration-2"

    from src.services.state_manager import AdvancedStateManager
    from src.services.session_service import save_state, get_state_manager as load_state

    manager = AdvancedStateManager(session_id=session_id)
    manager.set_variable("environment.danger_level", 3.0)
    save_state(manager, db_session)

    # We must seed a storylet or the API might fail because it generates a JIT or fallback
    # For a simple test, we just call the API. If JIT is hit, it will still trigger the tick on success.
    # To be safer, let's just make the request.
    payload = {"session_id": session_id, "storylet_id": None, "vars": {}}
    response = client.post("/api/next", json=payload)
    assert_ok_response(response)

    events = db_session.query(WorldEvent).filter_by(session_id=session_id, event_type=EVENT_TYPE_SIMULATION_TICK).all()

    assert len(events) == 1

    manager = load_state(session_id, db_session)
    assert manager.get_variable("environment.danger_level") == pytest.approx(3.1)


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
    turn_one = long_run_harness.TurnRecord(
        turn=1,
        phase="next",
        action_source="initial_scene",
        action_sent="",
        narrative="Neon rain glows over the market while drones sweep alley rooftops.",
        ack_line="",
        plausible=True,
        choices=[],
        state_changes={},
        vars={},
        diagnostics={},
        request_duration_ms=1.0,
        prefetch_wait_duration_ms=0.0,
        turn_duration_ms=1.0,
        request_status="ok",
        request_error="",
    )
    turn_two = long_run_harness.TurnRecord(
        turn=2,
        phase="next",
        action_source="choice_button",
        action_sent="explore",
        narrative="Neon lights cut through rain again as drones crowd the market edge.",
        ack_line="",
        plausible=True,
        choices=[],
        state_changes={},
        vars={},
        diagnostics={},
        request_duration_ms=1.0,
        prefetch_wait_duration_ms=0.0,
        turn_duration_ms=1.0,
        request_status="ok",
        request_error="",
    )
    metrics = long_run_harness._motif_reuse_metrics([turn_one, turn_two])
    assert metrics["motif_total_tokens"] > 0.0
    assert metrics["motif_overlap_count"] > 0.0
    assert metrics["motif_reuse_rate"] > 0.0
    assert isinstance(metrics["motif_top_reused"], list)
