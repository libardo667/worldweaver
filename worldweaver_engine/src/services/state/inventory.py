"""Inventory domain: ItemState dataclass and InventoryDomain manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ._types import StateChange, StateChangeType
from ._utils import _parse_dt


@dataclass
class ItemState:
    """Enhanced item representation with multiple states and properties."""

    id: str
    name: str
    description: str = ""
    quantity: int = 1
    condition: str = "good"
    properties: Dict[str, Any] = field(default_factory=dict)
    location: Optional[str] = None
    last_used: Optional[datetime] = None
    discovered_at: Optional[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))

    def can_combine_with(self, other: "ItemState") -> bool:
        """Check if this item can be combined with another."""
        combinable_with = self.properties.get("combinable_with", [])
        return other.id in combinable_with or other.name in combinable_with

    def get_available_actions(self, context: Dict[str, Any]) -> List[str]:
        """Get list of actions available with this item in current context."""
        actions = ["examine", "drop"]
        location = context.get("location", "")
        if self.properties.get("consumable", False):
            actions.append("use")
        if self.properties.get("equippable", False):
            actions.append("equip")
        if location == "workshop" and self.properties.get("craftable", False):
            actions.append("craft")
        return actions


class InventoryDomain:
    """Bounded inventory state: add/remove items with (result, StateChange) returns."""

    def __init__(self) -> None:
        self._items: Dict[str, ItemState] = {}

    @property
    def items(self) -> Dict[str, ItemState]:
        """Direct dict reference — same object every call."""
        return self._items

    def add(
        self,
        item_id: str,
        name: str,
        quantity: int = 1,
        properties: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ItemState, StateChange]:
        if item_id in self._items:
            self._items[item_id].quantity += quantity
            item = self._items[item_id]
        else:
            item = ItemState(
                id=item_id,
                name=name,
                quantity=quantity,
                properties=properties or {},
            )
            self._items[item_id] = item

        change = StateChange(
            change_type=StateChangeType.ITEM_ADD,
            variable=f"inventory.{item_id}",
            old_value=None,
            new_value=item,
            context=context or {},
        )
        return item, change

    def remove(self, item_id: str, quantity: int = 1) -> Tuple[bool, Optional[StateChange]]:
        if item_id not in self._items:
            return False, None

        item = self._items[item_id]
        actual_removed = min(quantity, item.quantity)
        old_item = ItemState(**item.__dict__)

        item.quantity -= actual_removed
        if item.quantity <= 0:
            del self._items[item_id]

        change = StateChange(
            change_type=StateChangeType.ITEM_REMOVE,
            variable=f"inventory.{item_id}",
            old_value=old_item,
            new_value=item if item.quantity > 0 else None,
        )
        return True, change

    def get(self, item_id: str) -> Optional[ItemState]:
        return self._items.get(item_id)

    def to_dict(self) -> Dict[str, Any]:
        def _dt(dt: Optional[datetime]) -> Optional[str]:
            return dt.isoformat() if dt else None

        result: Dict[str, Any] = {}
        for item_id, item in self._items.items():
            d = item.__dict__.copy()
            d["last_used"] = _dt(d.get("last_used"))
            d["discovered_at"] = _dt(d.get("discovered_at"))
            result[item_id] = d
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InventoryDomain":
        domain = cls()
        for item_id, item_data in data.items():
            d = dict(item_data)
            d["last_used"] = _parse_dt(d.get("last_used"))
            d["discovered_at"] = _parse_dt(d.get("discovered_at"))
            domain._items[item_id] = ItemState(**d)
        return domain
