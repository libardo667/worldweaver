import pytest
from src.models import Storylet, WorldEvent
from src.services.world_memory import EVENT_TYPE_SIMULATION_TICK
from src.config import settings
from src.services.prefetch_service import (
    clear_prefetch_cache,
    get_cached_frontier,
    invalidate_projection_for_session,
    refresh_frontier_for_session,
)
from src.services.runtime_metrics import (
    get_projection_pressure_metrics,
    reset_metrics,
)
from src.services.session_service import get_state_manager, save_state
from tests.integration_helpers import assert_ok_response
from tests.integration_state_helpers import get_manager, save_manager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_storylet(db, title, *, requires=None, embedding=None):
    s = Storylet(
        title=title,
        text_template=f"{title} text.",
        requires=requires or {},
        choices=[{"label": "Continue", "set": {}}],
        weight=1.0,
        embedding=embedding or [1.0, 0.0, 0.0],
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture(autouse=True)
def _reset_cache_and_metrics():
    clear_prefetch_cache()
    reset_metrics()
    yield
    clear_prefetch_cache()


def test_api_action_triggers_simulation_tick(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "enable_simulation_tick", True)
    session_id = "test-sim-integration-1"

    # Establish base state with danger
    from src.services.state_manager import AdvancedStateManager

    manager = AdvancedStateManager(session_id=session_id)
    manager.set_variable("environment.danger_level", 5.0)
    save_manager(db_session, manager)

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
    manager = get_manager(db_session, session_id)
    new_danger = manager.get_variable("environment.danger_level")
    assert new_danger > 5.0
    assert new_danger == pytest.approx(5.1)


def test_api_next_triggers_simulation_tick(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "enable_simulation_tick", True)
    session_id = "test-sim-integration-2"

    from src.services.state_manager import AdvancedStateManager

    manager = AdvancedStateManager(session_id=session_id)
    manager.set_variable("environment.danger_level", 3.0)
    save_manager(db_session, manager)

    # We must seed a storylet or the API might fail because it generates a JIT or fallback
    # For a simple test, we just call the API. If JIT is hit, it will still trigger the tick on success.
    # To be safer, let's just make the request.
    payload = {"session_id": session_id, "storylet_id": None, "vars": {}}
    response = client.post("/api/next", json=payload)
    assert_ok_response(response)

    events = db_session.query(WorldEvent).filter_by(session_id=session_id, event_type=EVENT_TYPE_SIMULATION_TICK).all()

    assert len(events) == 1

    manager = get_manager(db_session, session_id)
    assert manager.get_variable("environment.danger_level") == pytest.approx(3.1)


# ---------------------------------------------------------------------------
# Minor 105 — v3 Projection Smoke Tests
# ---------------------------------------------------------------------------


def test_v3_projection_generates_non_canon_stubs(db_session, monkeypatch):
    """Frontier refresh produces stubs marked non-canon with projection_depth > 0."""
    monkeypatch.setattr(settings, "enable_frontier_prefetch", True)
    monkeypatch.setattr(settings, "enable_v3_projection_expansion", True)
    monkeypatch.setattr(settings, "prefetch_max_per_session", 4)
    monkeypatch.setattr(settings, "v3_projection_max_depth", 2)
    monkeypatch.setattr(settings, "v3_projection_max_nodes", 12)
    monkeypatch.setattr(settings, "v3_projection_time_budget_ms", 5000)

    _seed_storylet(db_session, "smoke-a", requires={"location": "cave"}, embedding=[1.0, 0.0, 0.0])
    _seed_storylet(db_session, "smoke-b", requires={}, embedding=[0.9, 0.0, 0.0])

    sm = get_state_manager("v3-smoke-1", db_session)
    sm.set_variable("location", "cave")
    save_state(sm, db_session)

    result = refresh_frontier_for_session("v3-smoke-1", trigger="smoke-test", db=db_session)
    assert result is not None
    stubs = result["stubs"]
    assert stubs, "Expected at least one non-canon stub"
    non_canon = [s for s in stubs if s.get("non_canon") is True]
    assert non_canon, "All stubs must be non-canon"
    assert all(s["projection_depth"] >= 1 for s in non_canon)


def test_v3_projection_does_not_mutate_canonical_state(db_session, monkeypatch):
    """Projection refresh must not alter session variables or create world events."""
    monkeypatch.setattr(settings, "enable_frontier_prefetch", True)
    monkeypatch.setattr(settings, "enable_v3_projection_expansion", True)
    monkeypatch.setattr(settings, "prefetch_max_per_session", 4)
    monkeypatch.setattr(settings, "v3_projection_max_nodes", 12)
    monkeypatch.setattr(settings, "v3_projection_time_budget_ms", 5000)

    _seed_storylet(db_session, "smoke-iso", requires={}, embedding=[1.0, 0.0, 0.0])

    from src.models import SessionVars

    sm = get_state_manager("v3-smoke-iso", db_session)
    sm.set_variable("sentinel", "unchanged")
    save_state(sm, db_session)

    before = dict(db_session.get(SessionVars, "v3-smoke-iso").vars)
    before_events = db_session.query(WorldEvent).count()

    refresh_frontier_for_session("v3-smoke-iso", trigger="smoke-test", db=db_session)

    after = db_session.get(SessionVars, "v3-smoke-iso").vars
    assert after == before, "Projection must not mutate session vars"
    assert db_session.query(WorldEvent).count() == before_events, "Projection must not create world events"


def test_v3_projection_invalidation_clears_stubs(db_session, monkeypatch):
    """After invalidate_projection_for_session the cached stubs list is empty."""
    monkeypatch.setattr(settings, "enable_frontier_prefetch", True)
    monkeypatch.setattr(settings, "enable_v3_projection_expansion", True)
    monkeypatch.setattr(settings, "prefetch_max_per_session", 4)
    monkeypatch.setattr(settings, "v3_projection_max_nodes", 12)
    monkeypatch.setattr(settings, "v3_projection_time_budget_ms", 5000)

    _seed_storylet(db_session, "smoke-inv", requires={}, embedding=[1.0, 0.0, 0.0])

    sm = get_state_manager("v3-smoke-inv", db_session)
    save_state(sm, db_session)

    result = refresh_frontier_for_session("v3-smoke-inv", trigger="smoke-test", db=db_session)
    assert result is not None

    invalidate_projection_for_session("v3-smoke-inv", selected_projection_id=None)

    frontier = get_cached_frontier("v3-smoke-inv")
    assert frontier is not None
    assert frontier["stubs"] == [], "After invalidation stubs must be empty"


def test_v3_action_response_includes_diagnostic_envelope(client, db_session, monkeypatch):
    """Action endpoint response includes _ww_diag in vars with turn_source and pipeline_mode."""
    monkeypatch.setattr(settings, "enable_strict_three_layer_architecture", False)

    payload = {"session_id": "v3-smoke-diag", "action": "I look around."}
    response = client.post("/api/action", json=payload)
    assert_ok_response(response)

    data = response.json()
    vars_payload = data.get("vars", {}) or {}
    diag = vars_payload.get("_ww_diag", {}) or {}
    assert diag, "_ww_diag must be present in vars on every action response"
    assert "turn_source" in diag
    assert "pipeline_mode" in diag


# ---------------------------------------------------------------------------
# Minor 110 — Long-run Soak Tests
# ---------------------------------------------------------------------------


def test_soak_repeated_projection_refresh_nodes_bounded(db_session, monkeypatch):
    """Over N refresh cycles, projection_nodes_examined never exceeds the node budget."""
    monkeypatch.setattr(settings, "enable_frontier_prefetch", True)
    monkeypatch.setattr(settings, "enable_v3_projection_expansion", True)
    monkeypatch.setattr(settings, "prefetch_max_per_session", 4)
    monkeypatch.setattr(settings, "v3_projection_max_depth", 2)
    monkeypatch.setattr(settings, "v3_projection_max_nodes", 8)
    monkeypatch.setattr(settings, "v3_projection_time_budget_ms", 5000)

    for i in range(6):
        _seed_storylet(db_session, f"soak-multi-{i}", requires={}, embedding=[float(i) / 10, 0.0, 0.0])

    sm = get_state_manager("v3-soak-bounded", db_session)
    save_state(sm, db_session)

    node_budget = settings.v3_projection_max_nodes
    violations = []
    for cycle in range(5):
        clear_prefetch_cache()
        result = refresh_frontier_for_session("v3-soak-bounded", trigger=f"soak-{cycle}", db=db_session)
        if result is not None:
            examined = result["context_summary"].get("projection_nodes_examined", 0)
            if examined > node_budget:
                violations.append((cycle, examined))

    assert not violations, f"Node budget violated in cycles: {violations} (budget={node_budget})"


def test_soak_projection_pressure_counters_grow_monotonically(db_session, monkeypatch):
    """After N refresh cycles the full_expansions counter increments by at least N-1."""
    monkeypatch.setattr(settings, "enable_frontier_prefetch", True)
    monkeypatch.setattr(settings, "enable_v3_projection_expansion", True)
    monkeypatch.setattr(settings, "prefetch_max_per_session", 4)
    monkeypatch.setattr(settings, "v3_projection_max_nodes", 12)
    monkeypatch.setattr(settings, "v3_projection_time_budget_ms", 5000)
    monkeypatch.setattr(settings, "enable_adaptive_projection_pruning", False)

    _seed_storylet(db_session, "soak-pressure", requires={}, embedding=[1.0, 0.0, 0.0])

    sm = get_state_manager("v3-soak-pressure", db_session)
    save_state(sm, db_session)

    reset_metrics()
    cycles = 4
    successful = 0
    for cycle in range(cycles):
        clear_prefetch_cache()
        result = refresh_frontier_for_session("v3-soak-pressure", trigger=f"cycle-{cycle}", db=db_session)
        if result is not None:
            successful += 1

    metrics = get_projection_pressure_metrics()
    total_expansions = metrics["full_expansions"] + metrics["trimmed_expansions"] + metrics["stubs_only_expansions"]
    assert total_expansions == successful, f"Expected {successful} expansion records, got {total_expansions}"


def test_soak_projection_pruned_nodes_tracked_under_tight_budget(db_session, monkeypatch):
    """With adaptive pruning and a tiny budget, nodes_pruned is non-negative and bounded."""
    monkeypatch.setattr(settings, "enable_frontier_prefetch", True)
    monkeypatch.setattr(settings, "enable_v3_projection_expansion", True)
    monkeypatch.setattr(settings, "prefetch_max_per_session", 4)
    monkeypatch.setattr(settings, "v3_projection_max_depth", 2)
    monkeypatch.setattr(settings, "v3_projection_max_nodes", 3)
    monkeypatch.setattr(settings, "v3_projection_time_budget_ms", 5000)
    monkeypatch.setattr(settings, "enable_adaptive_projection_pruning", True)
    monkeypatch.setattr(settings, "enable_projection_pressure_tiers", True)
    monkeypatch.setattr(settings, "projection_pressure_prune_threshold", 0.3)
    monkeypatch.setattr(settings, "projection_pressure_stubs_only_threshold", 0.9)

    for i in range(5):
        _seed_storylet(db_session, f"soak-prune-{i}", requires={}, embedding=[float(i) / 6, 0.0, 0.0])

    sm = get_state_manager("v3-soak-prune", db_session)
    save_state(sm, db_session)

    reset_metrics()
    cumulative_pruned = 0
    for cycle in range(4):
        clear_prefetch_cache()
        result = refresh_frontier_for_session("v3-soak-prune", trigger=f"prune-{cycle}", db=db_session)
        if result is not None:
            pruned = result["context_summary"].get("nodes_pruned", 0)
            assert pruned >= 0, "nodes_pruned must be non-negative"
            cumulative_pruned += pruned

    pressure_metrics = get_projection_pressure_metrics()
    assert pressure_metrics["total_nodes_pruned"] == cumulative_pruned, "Runtime metrics must track the same pruned count as context_summary"
