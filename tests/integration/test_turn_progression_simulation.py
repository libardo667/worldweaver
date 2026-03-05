import pytest
from src.models import WorldEvent
from src.services.world_memory import EVENT_TYPE_SIMULATION_TICK
from src.config import settings

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
    payload = {
        "session_id": session_id,
        "action": "I wait patiently."
    }
    response = client.post("/api/action", json=payload)
    print("ACTION 422 DEBUG:", response.json() if response.status_code != 200 else "OK")
    assert response.status_code == 200
    
    # Verify simulation tick was recorded in world memory
    events = db_session.query(WorldEvent).filter_by(
        session_id=session_id,
        event_type=EVENT_TYPE_SIMULATION_TICK
    ).all()
    
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
    payload = {
        "session_id": session_id,
        "storylet_id": None,
        "vars": {}
    }
    response = client.post("/api/next", json=payload)
    print("NEXT 422 DEBUG:", response.json() if response.status_code != 200 else "OK")
    assert response.status_code == 200
    
    events = db_session.query(WorldEvent).filter_by(
        session_id=session_id,
        event_type=EVENT_TYPE_SIMULATION_TICK
    ).all()
    
    assert len(events) == 1
    
    manager = load_state(session_id, db_session)
    assert manager.get_variable("environment.danger_level") == pytest.approx(3.1)
