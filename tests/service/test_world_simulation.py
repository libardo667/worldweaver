from src.services.simulation.systems import EnvironmentDegradationSystem
from src.services.simulation.tick import tick_world_simulation
from src.services.state_manager import AdvancedStateManager
from src.config import settings


def test_environment_degradation_system_ignores_zero_danger():
    """Environment degradation should only apply if danger is > 0 and < 8."""
    system = EnvironmentDegradationSystem()
    manager = AdvancedStateManager(session_id="test-sim-1")
    manager.set_variable("environment.danger_level", 0.0)

    delta = system.evaluate(manager)
    assert delta is None


def test_environment_degradation_system_increments_active_danger():
    system = EnvironmentDegradationSystem()
    manager = AdvancedStateManager(session_id="test-sim-2")
    manager.set_variable("environment.danger_level", 1.0)

    delta = system.evaluate(manager)
    assert delta is not None
    assert len(delta.increment) == 1
    inc = delta.increment[0]
    assert inc.key == "environment.danger_level"
    assert inc.amount == 0.1


def test_tick_world_simulation_orchestrator(monkeypatch):
    monkeypatch.setattr(settings, "enable_simulation_tick", True)

    manager = AdvancedStateManager(session_id="test-sim-3")
    manager.set_variable("environment.danger_level", 2.0)

    aggregated_delta = tick_world_simulation(manager)

    assert len(aggregated_delta.increment) == 1
    assert aggregated_delta.increment[0].key == "environment.danger_level"


def test_tick_world_simulation_disabled_via_config(monkeypatch):
    monkeypatch.setattr(settings, "enable_simulation_tick", False)

    manager = AdvancedStateManager(session_id="test-sim-4")
    manager.set_variable("environment.danger_level", 2.0)

    aggregated_delta = tick_world_simulation(manager)

    # Empty contract when disabled
    assert len(aggregated_delta.increment) == 0
    assert len(aggregated_delta.set) == 0
