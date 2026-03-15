"""Relationship domain: RelationshipState dataclass and RelationshipDomain manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ._types import StateChange, StateChangeType
from ._utils import _parse_dt


@dataclass
class RelationshipState:
    """Multi-dimensional relationship tracking between entities."""

    entity_a: str
    entity_b: str
    trust: float = 0.0
    fear: float = 0.0
    attraction: float = 0.0
    respect: float = 0.0
    familiarity: float = 0.0
    last_interaction: Optional[datetime] = None
    interaction_count: int = 0
    memory_fragments: List[str] = field(default_factory=list)

    def get_overall_disposition(self) -> str:
        """Calculate overall relationship disposition."""
        total = self.trust + self.respect + self.attraction - self.fear
        if total > 150:
            return "devoted"
        elif total > 100:
            return "friendly"
        elif total > 50:
            return "positive"
        elif total > -50:
            return "neutral"
        elif total > -100:
            return "hostile"
        else:
            return "enemy"

    def add_memory(self, memory: str, max_memories: int = 10) -> None:
        """Add a memory fragment, keeping only recent ones."""
        self.memory_fragments.append(memory)
        if len(self.memory_fragments) > max_memories:
            self.memory_fragments.pop(0)

    def update(self, changes: Dict[str, float], memory: Optional[str] = None) -> None:
        """Update relationship attributes in batch."""
        for attr, value in changes.items():
            if hasattr(self, attr):
                current = getattr(self, attr)
                setattr(self, attr, current + value)

        self.interaction_count += 1
        self.last_interaction = datetime.now(timezone.utc)

        if memory:
            self.add_memory(memory)


class RelationshipDomain:
    """Bounded relationship state with alphabetical key normalization."""

    def __init__(self) -> None:
        self._items: Dict[str, RelationshipState] = {}

    @property
    def items(self) -> Dict[str, RelationshipState]:
        """Direct dict reference — same object every call."""
        return self._items

    @staticmethod
    def _rel_key(a: str, b: str) -> str:
        return f"{min(a, b)}:{max(a, b)}"

    def update(
        self,
        entity_a: str,
        entity_b: str,
        changes: Dict[str, float],
        memory: Optional[str] = None,
    ) -> Tuple[RelationshipState, StateChange]:
        rel_key = self._rel_key(entity_a, entity_b)

        if rel_key not in self._items:
            self._items[rel_key] = RelationshipState(entity_a, entity_b)

        rel = self._items[rel_key]
        old_state = RelationshipState(**rel.__dict__)

        # Apply changes with clamping to [-100, 100]
        for attr, change_amount in changes.items():
            if hasattr(rel, attr) and isinstance(change_amount, (int, float)):
                current = getattr(rel, attr)
                setattr(rel, attr, max(-100.0, min(100.0, current + float(change_amount))))
        rel.last_interaction = datetime.now(timezone.utc)
        rel.interaction_count += 1
        if memory:
            rel.add_memory(memory)

        change = StateChange(
            change_type=StateChangeType.RELATIONSHIP_CHANGE,
            variable=f"relationship.{rel_key}",
            old_value=old_state,
            new_value=rel,
        )
        return rel, change

    def get(self, entity_a: str, entity_b: str) -> Optional[RelationshipState]:
        return self._items.get(self._rel_key(entity_a, entity_b))

    def to_dict(self) -> Dict[str, Any]:
        def _dt(dt: Optional[datetime]) -> Optional[str]:
            return dt.isoformat() if dt else None

        result: Dict[str, Any] = {}
        for rel_key, rel in self._items.items():
            d = rel.__dict__.copy()
            d["last_interaction"] = _dt(d.get("last_interaction"))
            result[rel_key] = d
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelationshipDomain":
        domain = cls()
        for rel_key, rel_data in data.items():
            d = dict(rel_data)
            d["last_interaction"] = _parse_dt(d.get("last_interaction"))
            domain._items[rel_key] = RelationshipState(**d)
        return domain
