"""Migration fixture tests: v1/v2 snapshot loading and roundtrip (Minor 106)."""

from __future__ import annotations

import json
import os
import pytest

from src.services.state_manager import AdvancedStateManager
from tests.helpers.state_assertions import (
    assert_inventory_parity,
    assert_relationship_parity,
    assert_goal_parity,
    assert_export_import_roundtrip,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "state")


def _load(filename: str) -> dict:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def fixture_v2_full():
    return _load("v2_full_snapshot.json")


@pytest.fixture
def fixture_v1_flat():
    return _load("v1_flat_snapshot.json")


@pytest.fixture
def fixture_v2_partial():
    return _load("v2_partial_snapshot.json")


class TestV2FullSnapshot:
    def test_loads_all_domains(self, fixture_v2_full):
        manager = AdvancedStateManager("test")
        manager.import_state(fixture_v2_full)
        assert_inventory_parity(
            manager._inventory,
            {"sword": {"name": "Iron Sword", "quantity": 1}},
        )
        assert_relationship_parity(
            manager._relationships,
            {"innkeeper:player": {"trust": 20.0, "fear": 0.0}},
        )
        assert_goal_parity(
            manager._goals,
            {"primary_goal": "Find the stolen relic", "urgency": 0.4},
        )
        assert len(manager._beats.beats) == 1

    def test_roundtrip(self, fixture_v2_full):
        manager = AdvancedStateManager("test")
        manager.import_state(fixture_v2_full)
        assert_export_import_roundtrip(manager)


class TestV1FlatSnapshot:
    def test_leaves_typed_domains_empty(self, fixture_v1_flat):
        manager = AdvancedStateManager("test")
        # Legacy v1 path: variables dict is updated directly (no _v key)
        manager.variables.update(fixture_v1_flat)
        assert len(manager._inventory.items) == 0
        assert len(manager._relationships.items) == 0

    def test_variables_are_accessible(self, fixture_v1_flat):
        manager = AdvancedStateManager("test")
        manager.variables.update(fixture_v1_flat)
        assert manager.variables.get("location") == "village_square"


class TestV2PartialSnapshot:
    def test_produces_safe_defaults(self, fixture_v2_partial):
        manager = AdvancedStateManager("test")
        manager.import_state(fixture_v2_partial)
        assert manager._beats.to_dict() == []
        assert manager._goals.state.primary_goal == ""

    def test_empty_inventory_ok(self, fixture_v2_partial):
        manager = AdvancedStateManager("test")
        manager.import_state(fixture_v2_partial)
        assert len(manager._inventory.items) == 0

    def test_roundtrip(self, fixture_v2_partial):
        manager = AdvancedStateManager("test")
        manager.import_state(fixture_v2_partial)
        assert_export_import_roundtrip(manager)


class TestFailingMigration:
    def test_malformed_inventory_raises(self, fixture_v2_full):
        bad = dict(fixture_v2_full)
        # Unknown keyword arg causes TypeError during ItemState(**d) construction.
        bad["inventory"] = {"sword": {"id": "sword", "name": "ok", "unknown_field": True}}
        manager = AdvancedStateManager("test")
        with pytest.raises((ValueError, TypeError)):
            manager.import_state(bad)
