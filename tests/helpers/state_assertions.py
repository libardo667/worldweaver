"""Shared assertion helpers for state domain tests (Minor 106)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from src.services.state.inventory import InventoryDomain
    from src.services.state.relationships import RelationshipDomain
    from src.services.state.goals import GoalDomain
    from src.services.state_manager import AdvancedStateManager


def assert_inventory_parity(domain: "InventoryDomain", expected: Dict[str, Any]) -> None:
    """Assert domain.items matches expected {item_id: {name, quantity, ...}} shape."""
    assert set(domain.items.keys()) == set(expected.keys()), f"Inventory item keys mismatch. Got {set(domain.items.keys())}, expected {set(expected.keys())}"
    for item_id, exp_data in expected.items():
        item = domain.items[item_id]
        if "name" in exp_data:
            assert item.name == exp_data["name"], f"Item {item_id} name mismatch: got {item.name!r}, expected {exp_data['name']!r}"
        if "quantity" in exp_data:
            assert item.quantity == exp_data["quantity"], f"Item {item_id} quantity mismatch: got {item.quantity}, expected {exp_data['quantity']}"


def assert_relationship_parity(domain: "RelationshipDomain", expected: Dict[str, Any]) -> None:
    """Assert domain items match expected {rel_key: {trust, fear, ...}} shape."""
    assert set(domain.items.keys()) == set(expected.keys()), f"Relationship keys mismatch. Got {set(domain.items.keys())}, expected {set(expected.keys())}"
    for rel_key, exp_data in expected.items():
        rel = domain.items[rel_key]
        for attr in ("trust", "fear", "attraction", "respect", "familiarity"):
            if attr in exp_data:
                got = getattr(rel, attr)
                assert abs(got - float(exp_data[attr])) < 1e-6, f"Relationship {rel_key}.{attr}: got {got}, expected {exp_data[attr]}"


def assert_goal_parity(domain: "GoalDomain", expected: Dict[str, Any]) -> None:
    """Assert domain.state matches expected goal dict."""
    state = domain.state
    if "primary_goal" in expected:
        assert state.primary_goal == expected["primary_goal"], f"primary_goal mismatch: got {state.primary_goal!r}, expected {expected['primary_goal']!r}"
    if "urgency" in expected:
        assert abs(state.urgency - float(expected["urgency"])) < 1e-6, f"urgency mismatch: got {state.urgency}, expected {expected['urgency']}"
    if "complication" in expected:
        assert abs(state.complication - float(expected["complication"])) < 1e-6, f"complication mismatch: got {state.complication}, expected {expected['complication']}"


def assert_export_import_roundtrip(manager: "AdvancedStateManager") -> None:
    """Export state → fresh manager import → compare all 4 domain to_dict() outputs."""
    from src.services.state_manager import AdvancedStateManager

    exported = manager.export_state()
    fresh = AdvancedStateManager(manager.session_id)
    fresh.import_state(exported)

    assert fresh._inventory.to_dict() == manager._inventory.to_dict(), "Inventory roundtrip mismatch"
    assert fresh._relationships.to_dict() == manager._relationships.to_dict(), "Relationships roundtrip mismatch"
    assert fresh._goals.to_dict() == manager._goals.to_dict(), "Goals roundtrip mismatch"
    assert fresh._beats.to_dict() == manager._beats.to_dict(), "Beats roundtrip mismatch"


def assert_reducer_delta_applied(
    state_manager: "AdvancedStateManager",
    intent: Any,
    expected_applied_keys: List[str],
) -> None:
    """Verify all expected_applied_keys appear in the most recent change_history entries."""
    recent_vars = {change.variable for change in state_manager.change_history}
    for key in expected_applied_keys:
        assert key in recent_vars, f"Expected applied key {key!r} not found in change_history variables. Got: {recent_vars}"
