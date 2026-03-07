"""Domain isolation tests for InventoryDomain (Minor 106)."""

from datetime import datetime

from src.services.state.inventory import InventoryDomain
from src.services.state._types import StateChangeType
from tests.helpers.state_assertions import assert_inventory_parity


class TestInventoryDomainBasics:
    def test_add_new_item_returns_item_and_change(self):
        domain = InventoryDomain()
        item, change = domain.add("sword", "Iron Sword", quantity=1)
        assert item.id == "sword"
        assert item.name == "Iron Sword"
        assert item.quantity == 1
        assert change.change_type == StateChangeType.ITEM_ADD
        assert change.variable == "inventory.sword"

    def test_add_existing_item_stacks_quantity(self):
        domain = InventoryDomain()
        domain.add("potion", "Health Potion", quantity=2)
        item, _ = domain.add("potion", "Health Potion", quantity=3)
        assert item.quantity == 5

    def test_remove_item_returns_true_and_change(self):
        domain = InventoryDomain()
        domain.add("coin", "Gold Coin", quantity=10)
        success, change = domain.remove("coin", quantity=4)
        assert success is True
        assert domain.items["coin"].quantity == 6
        assert change.change_type == StateChangeType.ITEM_REMOVE

    def test_remove_all_deletes_item(self):
        domain = InventoryDomain()
        domain.add("key", "Rusty Key", quantity=1)
        success, change = domain.remove("key", quantity=5)
        assert success is True
        assert "key" not in domain.items
        assert change.new_value is None

    def test_remove_missing_item_returns_false_none(self):
        domain = InventoryDomain()
        success, change = domain.remove("ghost_item")
        assert success is False
        assert change is None

    def test_get_returns_item_or_none(self):
        domain = InventoryDomain()
        assert domain.get("nothing") is None
        domain.add("shield", "Wooden Shield")
        assert domain.get("shield") is not None

    def test_items_property_is_same_dict_reference(self):
        domain = InventoryDomain()
        ref1 = domain.items
        domain.add("map", "Treasure Map")
        ref2 = domain.items
        assert ref1 is ref2

    def test_to_dict_serializes_datetimes_as_strings(self):
        domain = InventoryDomain()
        domain.add("sword", "Iron Sword")
        data = domain.to_dict()
        assert "sword" in data
        discovered = data["sword"]["discovered_at"]
        assert isinstance(discovered, str)

    def test_from_dict_roundtrip(self):
        domain = InventoryDomain()
        domain.add("axe", "Battle Axe", quantity=2, properties={"combinable": False})
        serialized = domain.to_dict()
        restored = InventoryDomain.from_dict(serialized)
        assert restored.items["axe"].name == "Battle Axe"
        assert restored.items["axe"].quantity == 2

    def test_assert_inventory_parity_helper(self):
        domain = InventoryDomain()
        domain.add("ring", "Magic Ring", quantity=1)
        assert_inventory_parity(domain, {"ring": {"name": "Magic Ring", "quantity": 1}})

    def test_from_dict_handles_null_datetimes(self):
        data = {
            "torch": {
                "id": "torch",
                "name": "Torch",
                "description": "",
                "quantity": 3,
                "condition": "good",
                "properties": {},
                "location": None,
                "last_used": None,
                "discovered_at": "2026-01-01T00:00:00+00:00",
            }
        }
        domain = InventoryDomain.from_dict(data)
        assert domain.items["torch"].last_used is None
        assert isinstance(domain.items["torch"].discovered_at, datetime)
