"""Shared state-change types used by domain modules and the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class StateChangeType(Enum):
    SET = "set"
    INCREMENT = "increment"
    DECREMENT = "decrement"
    APPEND = "append"
    REMOVE = "remove"
    RELATIONSHIP_CHANGE = "relationship_change"
    ITEM_ADD = "item_add"
    ITEM_REMOVE = "item_remove"
    ITEM_MODIFY = "item_modify"


@dataclass
class StateChange:
    """Record of a single state mutation."""

    change_type: StateChangeType
    variable: str
    old_value: Any
    new_value: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = field(default_factory=dict)
    storylet_id: Optional[int] = None
