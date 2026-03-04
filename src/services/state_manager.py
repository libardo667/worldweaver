"""
Advanced State Management System for WorldWeaver

This module provides sophisticated state tracking capabilities inspired by
successful Twine games like "The Play" (relationships), "Hallowmoor" (inventory),
and environmental storytelling techniques.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta, timezone
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import logging

from ..models import NarrativeBeat
from .requirements import evaluate_requirement_value, evaluate_requirements

logger = logging.getLogger(__name__)


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse an ISO datetime string (or None) back to a datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


class StateChangeType(Enum):
    """Types of state changes for tracking and rollback."""

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
    """Records a single state change for history tracking."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    change_type: StateChangeType = StateChangeType.SET
    variable: str = ""
    old_value: Any = None
    new_value: Any = None
    context: Dict[str, Any] = field(default_factory=dict)
    storylet_id: Optional[int] = None


@dataclass
class ItemState:
    """Enhanced item representation with multiple states and properties."""

    id: str
    name: str
    description: str = ""
    quantity: int = 1
    condition: str = "good"  # good, worn, broken, magical, etc.
    properties: Dict[str, Any] = field(default_factory=dict)
    location: Optional[str] = None  # where item is stored
    last_used: Optional[datetime] = None
    discovered_at: Optional[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))

    def can_combine_with(self, other: "ItemState") -> bool:
        """Check if this item can be combined with another."""
        # Basic combination rules - can be extended
        combinable_with = self.properties.get("combinable_with", [])
        return other.id in combinable_with or other.name in combinable_with

    def get_available_actions(self, context: Dict[str, Any]) -> List[str]:
        """Get list of actions available with this item in current context."""
        actions = ["examine", "drop"]

        # Context-sensitive actions
        location = context.get("location", "")
        if self.properties.get("consumable", False):
            actions.append("use")
        if self.properties.get("equippable", False):
            actions.append("equip")
        if location == "workshop" and self.properties.get("craftable", False):
            actions.append("craft")

        return actions


@dataclass
class RelationshipState:
    """Complex relationship tracking between entities."""

    entity_a: str
    entity_b: str
    trust: float = 0.0  # -100 to 100
    fear: float = 0.0  # 0 to 100
    attraction: float = 0.0  # -100 to 100
    respect: float = 0.0  # -100 to 100
    familiarity: float = 0.0  # 0 to 100
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

    def add_memory(self, memory: str, max_memories: int = 10):
        """Add a memory fragment, keeping only recent ones."""
        self.memory_fragments.append(memory)
        if len(self.memory_fragments) > max_memories:
            self.memory_fragments.pop(0)

    def update(self, changes: Dict[str, float], memory: Optional[str] = None):
        """Update relationship attributes in batch."""
        for attr, value in changes.items():
            if hasattr(self, attr):
                current = getattr(self, attr)
                setattr(self, attr, current + value)

        self.interaction_count += 1
        self.last_interaction = datetime.now(timezone.utc)

        if memory:
            self.add_memory(memory)


@dataclass
class EnvironmentalState:
    """Environmental factors that affect gameplay."""

    time_of_day: str = "morning"  # morning, afternoon, evening, night
    weather: str = "clear"  # clear, cloudy, rainy, stormy, snowy
    season: str = "spring"  # spring, summer, autumn, winter
    temperature: int = 20  # Celsius
    danger_level: int = 0  # 0-10 scale
    noise_level: int = 0  # 0-10 scale
    lighting: str = "bright"  # dark, dim, bright, brilliant
    air_quality: str = "fresh"  # fresh, stale, toxic, magical

    def get_mood_modifier(self) -> Dict[str, float]:
        """Get mood modifiers based on environment."""
        modifiers = {}

        # Weather effects
        if self.weather == "rainy":
            modifiers["melancholy"] = 0.2
        elif self.weather == "stormy":
            modifiers["tension"] = 0.3
        elif self.weather == "clear":
            modifiers["optimism"] = 0.1

        # Time effects
        if self.time_of_day == "night":
            modifiers["fear"] = 0.1
            modifiers["mystery"] = 0.2
        elif self.time_of_day == "morning":
            modifiers["energy"] = 0.1

        return modifiers

    def update(self, changes: Dict[str, Any]):
        """Update environmental attributes in batch."""
        for attr, value in changes.items():
            if hasattr(self, attr):
                setattr(self, attr, value)


@dataclass
class GoalMilestone:
    """Single timeline event tied to the player's narrative goal arc."""

    title: str
    status: str = "progressed"
    note: str = ""
    source: str = "system"
    urgency_delta: float = 0.0
    complication_delta: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "status": self.status,
            "note": self.note,
            "source": self.source,
            "urgency_delta": float(self.urgency_delta),
            "complication_delta": float(self.complication_delta),
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GoalMilestone":
        timestamp = _parse_dt(payload.get("timestamp")) or datetime.now(timezone.utc)
        return cls(
            title=str(payload.get("title", "Milestone")).strip() or "Milestone",
            status=str(payload.get("status", "progressed")),
            note=str(payload.get("note", "")),
            source=str(payload.get("source", "system")),
            urgency_delta=float(payload.get("urgency_delta", 0.0)),
            complication_delta=float(payload.get("complication_delta", 0.0)),
            timestamp=timestamp,
        )


@dataclass
class GoalState:
    """Structured player goal and arc tracking state."""

    primary_goal: str = ""
    subgoals: List[str] = field(default_factory=list)
    urgency: float = 0.0
    complication: float = 0.0
    milestones: List[GoalMilestone] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_goal": self.primary_goal,
            "subgoals": list(self.subgoals),
            "urgency": float(self.urgency),
            "complication": float(self.complication),
            "updated_at": self.updated_at.isoformat(),
            "milestones": [milestone.to_dict() for milestone in self.milestones],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GoalState":
        milestones_payload = payload.get("milestones", [])
        milestones: List[GoalMilestone] = []
        if isinstance(milestones_payload, list):
            for item in milestones_payload[:50]:
                if isinstance(item, dict):
                    milestones.append(GoalMilestone.from_dict(item))

        updated_at = _parse_dt(payload.get("updated_at")) or datetime.now(timezone.utc)
        subgoals_payload = payload.get("subgoals", [])
        subgoals: List[str] = []
        if isinstance(subgoals_payload, list):
            subgoals = [
                str(item).strip()
                for item in subgoals_payload[:10]
                if str(item).strip()
            ]
        return cls(
            primary_goal=str(payload.get("primary_goal", "")).strip(),
            subgoals=subgoals,
            urgency=max(0.0, min(1.0, float(payload.get("urgency", 0.0)))),
            complication=max(0.0, min(1.0, float(payload.get("complication", 0.0)))),
            milestones=milestones,
            updated_at=updated_at,
        )


class AdvancedStateManager:
    """
    Sophisticated state management system that tracks:
    - Complex variable relationships
    - Multi-dimensional inventory
    - NPC relationships and memories
    - Environmental conditions
    - State change history
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.variables = {}
        self.inventory = {}
        self.relationships = {}
        self.goal_state = GoalState()
        self.active_narrative_beats: List[NarrativeBeat] = []
        self.environment = EnvironmentalState()
        self.change_history = deque(maxlen=200)
        self.context_stack = []

        # Performance optimization: cache frequently accessed computations
        self._cached_computations = {}
        self._cache_expiry = datetime.now(timezone.utc)

    def set_variable(
        self,
        key: str,
        value: Any,
        context: Optional[Dict[str, Any]] = None,
        storylet_id: Optional[int] = None,
    ) -> Any:
        """Set a variable with full history tracking."""
        old_value = self.variables.get(key)

        # Record the change
        change = StateChange(
            change_type=StateChangeType.SET,
            variable=key,
            old_value=old_value,
            new_value=value,
            context=context or {},
            storylet_id=storylet_id,
        )
        self.change_history.append(change)

        # Apply the change
        self.variables[key] = value
        self._invalidate_cache()

        logger.debug(f"Variable '{key}' changed from {old_value} to {value}")
        return value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a variable value with optional default."""
        return self.variables.get(key, default)

    def increment_variable(
        self,
        key: str,
        amount: Union[int, float] = 1,
        context: Optional[Dict[str, Any]] = None,
        storylet_id: Optional[int] = None,
    ) -> Any:
        """Increment a numeric variable."""
        current = self.variables.get(key, 0)
        new_value = current + amount

        change = StateChange(
            change_type=StateChangeType.INCREMENT,
            variable=key,
            old_value=current,
            new_value=new_value,
            context=context or {},
            storylet_id=storylet_id,
        )
        self.change_history.append(change)

        self.variables[key] = new_value
        self._invalidate_cache()
        return new_value

    def add_item(
        self,
        item_id: str,
        name: str,
        quantity: int = 1,
        properties: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ItemState:
        """Add an item to inventory with full state tracking."""
        if item_id in self.inventory:
            # Item exists, increase quantity
            self.inventory[item_id].quantity += quantity
            item = self.inventory[item_id]
        else:
            # New item
            item = ItemState(
                id=item_id, name=name, quantity=quantity, properties=properties or {}
            )
            self.inventory[item_id] = item

        change = StateChange(
            change_type=StateChangeType.ITEM_ADD,
            variable=f"inventory.{item_id}",
            old_value=None,
            new_value=item,
            context=context or {},
        )
        self.change_history.append(change)

        logger.debug(f"Added {quantity}x {name} to inventory")
        return item

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        """Remove items from inventory. Returns True if any items were removed."""
        if item_id not in self.inventory:
            return False

        item = self.inventory[item_id]
        original_quantity = item.quantity

        # Allow removing more than available (remove all)
        actual_removed = min(quantity, item.quantity)

        old_item = ItemState(**item.__dict__)  # Copy for history

        item.quantity -= actual_removed
        if item.quantity <= 0:
            del self.inventory[item_id]

        change = StateChange(
            change_type=StateChangeType.ITEM_REMOVE,
            variable=f"inventory.{item_id}",
            old_value=old_item,
            new_value=item if item.quantity > 0 else None,
        )
        self.change_history.append(change)

        logger.debug(f"Removed {actual_removed}x {item.name} from inventory")
        return True

    def update_relationship(
        self,
        entity_a: str,
        entity_b: str,
        changes: Dict[str, float],
        memory: Optional[str] = None,
    ) -> RelationshipState:
        """Update relationship between two entities."""
        # Create a standardized relationship key (alphabetical order)
        rel_key = f"{min(entity_a, entity_b)}:{max(entity_a, entity_b)}"

        if rel_key not in self.relationships:
            self.relationships[rel_key] = RelationshipState(entity_a, entity_b)

        rel = self.relationships[rel_key]
        old_state = RelationshipState(**rel.__dict__)  # Copy for history

        # Apply changes
        for attribute, change_amount in changes.items():
            if hasattr(rel, attribute):
                current_value = getattr(rel, attribute)
                new_value = max(
                    -100, min(100, current_value + change_amount)
                )  # Clamp to -100/100
                setattr(rel, attribute, new_value)

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
        self.change_history.append(change)

        logger.debug(f"Updated relationship {entity_a}-{entity_b}: {changes}")
        return rel

    def get_relationship(
        self, entity_a: str, entity_b: str
    ) -> Optional[RelationshipState]:
        """Get relationship between two entities."""
        rel_key = f"{min(entity_a, entity_b)}:{max(entity_a, entity_b)}"
        return self.relationships.get(rel_key)

    def update_environment(self, changes: Dict[str, Any]):
        """Update environmental conditions."""
        for key, value in changes.items():
            if hasattr(self.environment, key):
                setattr(self.environment, key, value)

        self._invalidate_cache()
        logger.debug(f"Updated environment: {changes}")

    def _clamp_goal_signal(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _record_goal_milestone(
        self,
        title: str,
        status: str,
        *,
        note: str = "",
        source: str = "system",
        urgency_delta: float = 0.0,
        complication_delta: float = 0.0,
    ) -> GoalMilestone:
        milestone = GoalMilestone(
            title=str(title).strip() or "Milestone",
            status=str(status or "progressed"),
            note=str(note or ""),
            source=str(source or "system"),
            urgency_delta=float(urgency_delta),
            complication_delta=float(complication_delta),
        )
        self.goal_state.milestones.append(milestone)
        if len(self.goal_state.milestones) > 50:
            self.goal_state.milestones = self.goal_state.milestones[-50:]
        self.goal_state.updated_at = datetime.now(timezone.utc)
        self._invalidate_cache()
        return milestone

    def set_goal_state(
        self,
        *,
        primary_goal: Optional[str] = None,
        subgoals: Optional[List[str]] = None,
        urgency: Optional[float] = None,
        complication: Optional[float] = None,
        note: Optional[str] = None,
        source: str = "player",
    ) -> Dict[str, Any]:
        """Create or update structured goal state."""
        changed = False
        if primary_goal is not None:
            cleaned = str(primary_goal).strip()
            if cleaned and cleaned != self.goal_state.primary_goal:
                self.goal_state.primary_goal = cleaned
                changed = True
                self._record_goal_milestone(
                    title=f"Primary goal set: {cleaned}",
                    status="branched",
                    note=str(note or ""),
                    source=source,
                )

        if subgoals is not None:
            cleaned_subgoals = [
                str(goal).strip()
                for goal in subgoals[:10]
                if str(goal).strip()
            ]
            self.goal_state.subgoals = cleaned_subgoals
            changed = True

        if urgency is not None:
            self.goal_state.urgency = self._clamp_goal_signal(float(urgency))
            changed = True

        if complication is not None:
            self.goal_state.complication = self._clamp_goal_signal(float(complication))
            changed = True

        if changed:
            self.goal_state.updated_at = datetime.now(timezone.utc)
            self._invalidate_cache()

        return self.get_goal_state()

    def add_goal_subgoal(self, subgoal: str, source: str = "system") -> None:
        cleaned = str(subgoal).strip()
        if not cleaned:
            return
        if cleaned not in self.goal_state.subgoals:
            self.goal_state.subgoals.append(cleaned)
            self.goal_state.subgoals = self.goal_state.subgoals[:10]
            self._record_goal_milestone(
                title=f"New subgoal: {cleaned}",
                status="branched",
                source=source,
            )

    def mark_goal_milestone(
        self,
        title: str,
        *,
        status: str = "progressed",
        note: str = "",
        source: str = "system",
        urgency_delta: float = 0.0,
        complication_delta: float = 0.0,
    ) -> Dict[str, Any]:
        """Append a milestone and update urgency/complication signals."""
        self.goal_state.urgency = self._clamp_goal_signal(
            self.goal_state.urgency + float(urgency_delta)
        )
        self.goal_state.complication = self._clamp_goal_signal(
            self.goal_state.complication + float(complication_delta)
        )
        self._record_goal_milestone(
            title=title,
            status=status,
            note=note,
            source=source,
            urgency_delta=urgency_delta,
            complication_delta=complication_delta,
        )
        return self.get_goal_state()

    def apply_goal_update(
        self,
        update: Dict[str, Any],
        *,
        source: str = "system",
    ) -> Dict[str, Any]:
        """Apply goal changes from action interpretation metadata."""
        if not isinstance(update, dict):
            return self.get_goal_state()

        milestone_title = str(update.get("milestone") or "").strip()
        status = str(update.get("status") or "progressed").strip() or "progressed"
        note = str(update.get("note") or "").strip()
        urgency_delta = float(update.get("urgency_delta", 0.0) or 0.0)
        complication_delta = float(update.get("complication_delta", 0.0) or 0.0)
        subgoal = str(update.get("subgoal") or "").strip()

        primary_goal = update.get("primary_goal")
        if primary_goal is not None:
            self.set_goal_state(
                primary_goal=str(primary_goal),
                source=source,
                note=note,
            )

        if subgoal:
            self.add_goal_subgoal(subgoal, source=source)

        if milestone_title or urgency_delta or complication_delta:
            self.mark_goal_milestone(
                milestone_title or "Goal state adjusted",
                status=status,
                note=note,
                source=source,
                urgency_delta=urgency_delta,
                complication_delta=complication_delta,
            )

        return self.get_goal_state()

    def get_goal_state(self) -> Dict[str, Any]:
        """Return goal state suitable for API responses/persistence."""
        return self.goal_state.to_dict()

    def get_arc_timeline(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent arc milestones newest-first."""
        recent = self.goal_state.milestones[-max(1, int(limit)):]
        return [milestone.to_dict() for milestone in reversed(recent)]

    def get_goal_embedding_context(self) -> str:
        """Dense text context that can be embedded for semantic scoring."""
        if not self.goal_state.primary_goal:
            return ""

        parts = [f"Primary goal: {self.goal_state.primary_goal}"]
        if self.goal_state.subgoals:
            parts.append("Subgoals: " + ", ".join(self.goal_state.subgoals[:5]))
        parts.append(
            f"Goal urgency={self.goal_state.urgency:.2f}, complication={self.goal_state.complication:.2f}"
        )
        if self.goal_state.milestones:
            milestone_text = "; ".join(
                f"{m.status}: {m.title}" for m in self.goal_state.milestones[-3:]
            )
            parts.append("Recent arc milestones: " + milestone_text)
        return " ".join(parts)

    def add_narrative_beat(self, beat: Union[NarrativeBeat, Dict[str, Any]]) -> None:
        """Add or refresh a narrative beat that steers semantic selection."""
        normalized = beat if isinstance(beat, NarrativeBeat) else NarrativeBeat.from_dict(beat)
        normalized.name = str(normalized.name or "").strip() or "ThematicResonance"
        normalized.intensity = max(0.0, float(normalized.intensity))
        normalized.turns_remaining = max(0, int(normalized.turns_remaining))
        normalized.decay = max(0.0, min(1.0, float(normalized.decay)))
        if not normalized.is_active():
            return

        for idx, existing in enumerate(self.active_narrative_beats):
            if existing.name.lower() == normalized.name.lower():
                merged = NarrativeBeat(
                    name=existing.name,
                    intensity=max(0.0, float(existing.intensity) + float(normalized.intensity)),
                    turns_remaining=max(existing.turns_remaining, normalized.turns_remaining),
                    decay=min(float(existing.decay), float(normalized.decay)),
                    vector=normalized.vector or existing.vector,
                    source=normalized.source or existing.source,
                )
                self.active_narrative_beats[idx] = merged
                self._invalidate_cache()
                return

        self.active_narrative_beats.append(normalized)
        self._invalidate_cache()

    def get_active_narrative_beats(self) -> List[NarrativeBeat]:
        """Return currently active beats."""
        self.active_narrative_beats = [beat for beat in self.active_narrative_beats if beat.is_active()]
        return list(self.active_narrative_beats)

    def decay_narrative_beats(self) -> None:
        """Decay active narrative beats by one turn."""
        if not self.active_narrative_beats:
            return

        for beat in self.active_narrative_beats:
            beat.consume_turn()
        self.active_narrative_beats = [beat for beat in self.active_narrative_beats if beat.is_active()]
        self._invalidate_cache()

    def apply_world_delta(self, delta: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Apply a world-event delta to persistent state.

        Supported shapes:
        - Flat variable updates: {"bridge_broken": true}
        - Nested variable updates: {"variables": {...}}
        - Environment updates: {"environment": {"weather": "stormy"}}
        - Spatial node metadata: {"spatial_nodes": {"bridge": {"broken": true}}}
        """
        applied: Dict[str, Dict[str, Any]] = {
            "variables": {},
            "environment": {},
            "spatial_nodes": {},
        }
        if not isinstance(delta, dict) or not delta:
            return applied

        env_changes = delta.get("environment")
        if isinstance(env_changes, dict) and env_changes:
            filtered = {
                key: value
                for key, value in env_changes.items()
                if hasattr(self.environment, key)
            }
            if filtered:
                self.update_environment(filtered)
                applied["environment"] = filtered

        spatial_changes = delta.get("spatial_nodes")
        if isinstance(spatial_changes, dict) and spatial_changes:
            existing_spatial = self.get_variable("spatial_nodes", {})
            if not isinstance(existing_spatial, dict):
                existing_spatial = {}
            merged_spatial = dict(existing_spatial)
            merged_spatial.update(spatial_changes)
            self.set_variable("spatial_nodes", merged_spatial)
            applied["spatial_nodes"] = spatial_changes

        variable_changes: Dict[str, Any] = {}
        nested_vars = delta.get("variables")
        if isinstance(nested_vars, dict):
            variable_changes.update(nested_vars)

        for key, value in delta.items():
            if key in {"variables", "environment", "spatial_nodes", "__action_meta__"}:
                continue
            variable_changes[str(key)] = value

        for key, value in variable_changes.items():
            self.set_variable(key, value)
            applied["variables"][key] = value

        return applied

    def evaluate_condition(self, condition: Dict[str, Any]) -> bool:
        """
        Enhanced condition evaluation supporting:
        - Relationship queries: {'relationship:player:npc': {'trust': {'gte': 50}}}
        - Item queries: {'item:sword': {'condition': 'good', 'quantity': {'gte': 1}}}
        - Environmental queries: {'environment': {'weather': 'rainy'}}
        - Complex combinations
        """
        for key, requirements in condition.items():

            # Relationship conditions
            if key.startswith("relationship:"):
                _, entity_a, entity_b = key.split(":")
                rel = self.get_relationship(entity_a, entity_b)
                if not rel:
                    return False

                for attr, req in requirements.items():
                    rel_value = getattr(rel, attr, 0)
                    if not evaluate_requirement_value(rel_value, req):
                        return False

            # Item conditions
            elif key.startswith("item:"):
                _, item_id = key.split(":", 1)
                item = self.inventory.get(item_id)
                if not item:
                    return False

                for attr, req in requirements.items():
                    if attr == "quantity":
                        if not evaluate_requirement_value(item.quantity, req):
                            return False
                    else:
                        item_value = getattr(item, attr, None)
                        if not evaluate_requirement_value(item_value, req):
                            return False

            # Environment conditions
            elif key == "environment":
                for attr, req in requirements.items():
                    env_value = getattr(self.environment, attr, None)
                    if not evaluate_requirement_value(env_value, req):
                        return False

            # Standard variable conditions
            else:
                if not evaluate_requirements(
                    {key: requirements},
                    self.variables,
                    allow_flexible_location=True,
                    numeric_fallback_gte=True,
                ):
                    return False

        return True

    def get_contextual_variables(self) -> Dict[str, Any]:
        """Get all variables plus computed contextual information."""
        cache_key = "contextual_vars"
        if (
            cache_key in self._cached_computations
            and datetime.now(timezone.utc) < self._cache_expiry
        ):
            return self._cached_computations[cache_key]

        # Base variables
        context: Dict[str, Any] = dict(self.variables)

        # Add computed values
        context["_inventory_count"] = len(self.inventory)
        context["_total_item_quantity"] = sum(
            item.quantity for item in self.inventory.values()
        )
        context["_relationship_count"] = len(self.relationships)
        context["_time_of_day"] = self.environment.time_of_day
        context["_weather"] = self.environment.weather
        context["_danger_level"] = self.environment.danger_level

        # Add non-underscore versions for compatibility
        context["inventory_count"] = len(self.inventory)
        context["total_item_quantity"] = sum(
            item.quantity for item in self.inventory.values()
        )
        context["relationship_count"] = len(self.relationships)
        context["time_of_day"] = self.environment.time_of_day
        context["weather"] = self.environment.weather
        context["danger_level"] = self.environment.danger_level
        context["inventory_items"] = list(self.inventory.keys())
        context["known_people"] = list(
            {
                rel.entity_a if rel.entity_a != "player" else rel.entity_b
                for rel in self.relationships.values()
            }
        )
        context["goal_primary"] = self.goal_state.primary_goal
        context["goal_subgoals"] = list(self.goal_state.subgoals[:5])
        context["goal_urgency"] = float(self.goal_state.urgency)
        context["goal_complication"] = float(self.goal_state.complication)

        # Add mood modifiers from environment
        mood_modifiers = self.environment.get_mood_modifier()
        for mood, modifier in mood_modifiers.items():
            context[f"_mood_{mood}"] = modifier

        # Cache the result
        self._cached_computations[cache_key] = context
        self._cache_expiry = datetime.now(timezone.utc) + timedelta(seconds=30)

        return context

    def _invalidate_cache(self):
        """Clear cached computations when state changes."""
        self._cached_computations.clear()
        self._cache_expiry = datetime.now(timezone.utc)

    def get_state_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of current state."""
        inventory_summary = {
            "total_items": len(self.inventory),
            "total_quantity": sum(item.quantity for item in self.inventory.values()),
            "items": {
                item_id: {
                    "name": item.name,
                    "quantity": item.quantity,
                    "condition": item.condition,
                }
                for item_id, item in self.inventory.items()
            },
        }

        relationships_summary = {
            rel_key: {
                "disposition": rel.get_overall_disposition(),
                "trust": rel.trust,
                "respect": rel.respect,
                "interaction_count": rel.interaction_count,
            }
            for rel_key, rel in self.relationships.items()
        }

        return {
            "session_id": self.session_id,
            "variables": self.variables,
            "inventory": inventory_summary,  # Add expected key
            "inventory_summary": inventory_summary,  # Keep for backward compatibility
            "relationships": relationships_summary,  # Add expected key
            "relationships_summary": relationships_summary,  # Keep for backward compatibility
            "goal": self.get_goal_state(),
            "arc_timeline": self.get_arc_timeline(limit=20),
            "environment": {
                "time_of_day": self.environment.time_of_day,
                "weather": self.environment.weather,
                "danger_level": self.environment.danger_level,
                "mood_modifiers": self.environment.get_mood_modifier(),
            },
            "stats": {
                "total_variables": len(self.variables),
                "total_items": len(self.inventory),
                "total_relationships": len(self.relationships),
            },
            "recent_changes": len(
                [
                    c
                    for c in self.change_history
                    if c.timestamp > datetime.now(timezone.utc) - timedelta(minutes=5)
                ]
            ),
        }

    def export_state(self) -> Dict[str, Any]:
        """Export complete state as a JSON-serializable dict.

        Returns a v2 payload that includes inventory, relationships, and
        environment — not just flat variables.  All datetime values are
        converted to ISO-format strings so the result can be stored directly
        in the JSON column of SessionVars.  change_history is intentionally
        omitted because old_value/new_value can hold arbitrary objects.
        """
        def _dt(dt: Optional[datetime]) -> Optional[str]:
            return dt.isoformat() if dt else None

        inventory_data: Dict[str, Any] = {}
        for item_id, item in self.inventory.items():
            d = item.__dict__.copy()
            d["last_used"] = _dt(d.get("last_used"))
            d["discovered_at"] = _dt(d.get("discovered_at"))
            inventory_data[item_id] = d

        relationships_data: Dict[str, Any] = {}
        for rel_key, rel in self.relationships.items():
            d = rel.__dict__.copy()
            d["last_interaction"] = _dt(d.get("last_interaction"))
            relationships_data[rel_key] = d

        return {
            "_v": 2,
            "session_id": self.session_id,
            "variables": self.variables,
            "inventory": inventory_data,
            "relationships": relationships_data,
            "goal_state": self.goal_state.to_dict(),
            "environment": self.environment.__dict__.copy(),
            "narrative_beats": [beat.to_dict() for beat in self.active_narrative_beats if beat.is_active()],
        }

    def import_state(self, state_data: Dict[str, Any]):
        """Import state from a v2 export_state() payload.

        Handles datetime strings produced by export_state() and is safe to
        call with an empty or partial payload (missing keys default to their
        initial values).
        """
        self.session_id = state_data.get("session_id", self.session_id)
        self.variables = state_data.get("variables", {})

        # Reconstruct inventory, converting ISO datetime strings back.
        self.inventory = {}
        for item_id, item_data in state_data.get("inventory", {}).items():
            d = dict(item_data)
            d["last_used"] = _parse_dt(d.get("last_used"))
            d["discovered_at"] = _parse_dt(d.get("discovered_at"))
            self.inventory[item_id] = ItemState(**d)

        # Reconstruct relationships, converting ISO datetime strings back.
        self.relationships = {}
        for rel_key, rel_data in state_data.get("relationships", {}).items():
            d = dict(rel_data)
            d["last_interaction"] = _parse_dt(d.get("last_interaction"))
            self.relationships[rel_key] = RelationshipState(**d)

        # Reconstruct environment.
        if "environment" in state_data:
            self.environment = EnvironmentalState(**state_data["environment"])

        goal_payload = state_data.get("goal_state", {})
        if isinstance(goal_payload, dict):
            self.goal_state = GoalState.from_dict(goal_payload)
        else:
            self.goal_state = GoalState()

        self.active_narrative_beats = []
        for beat_payload in state_data.get("narrative_beats", []):
            if not isinstance(beat_payload, dict):
                continue
            try:
                self.add_narrative_beat(NarrativeBeat.from_dict(beat_payload))
            except Exception:
                continue

        # change_history is not persisted (v2 omits it intentionally).
        self.change_history = deque(maxlen=200)

        self._invalidate_cache()
        logger.info(f"Imported state for session {self.session_id}")

    # -----------------------------------------------------------------------
    # JIT BEAT PIPELINE — world bible and story arc helpers
    # -----------------------------------------------------------------------

    _WORLD_BIBLE_KEY = "_world_bible"
    _STORY_ARC_KEY = "_story_arc"

    # Act promotion thresholds (turn counts)
    _ARC_THRESHOLDS = {
        "setup": 3,          # → rising_action after 3 beats
        "rising_action": 8,  # → climax after 8 beats
        "climax": 14,        # → resolution after 14 beats
    }
    _ARC_PROGRESSION = ["setup", "rising_action", "climax", "resolution"]

    def set_world_bible(self, bible: Dict[str, Any]) -> None:
        """Persist the world bible dict into session state.

        Uses an underscore-prefixed key so it survives export_state/import_state
        without any schema changes.
        """
        if not isinstance(bible, dict):
            raise TypeError(f"world_bible must be a dict, got {type(bible).__name__}")
        self.variables[self._WORLD_BIBLE_KEY] = bible
        self._invalidate_cache()
        logger.debug("World bible stored for session %s", self.session_id)

    def get_world_bible(self) -> Optional[Dict[str, Any]]:
        """Return the stored world bible, or None if not yet generated."""
        value = self.variables.get(self._WORLD_BIBLE_KEY)
        return value if isinstance(value, dict) else None

    def get_story_arc(self) -> Dict[str, Any]:
        """Return the current story arc state, initialising it if absent."""
        arc = self.variables.get(self._STORY_ARC_KEY)
        if not isinstance(arc, dict):
            arc = {
                "act": "setup",
                "tension": "",
                "turn_count": 0,
                "unresolved_threads": [],
            }
            self.variables[self._STORY_ARC_KEY] = arc
            self._invalidate_cache()
        return dict(arc)

    def advance_story_arc(
        self,
        choices_made: Optional[List[Dict[str, Any]]] = None,
        tension: Optional[str] = None,
        unresolved_threads: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Increment turn_count, promote act, and update tension/threads.

        Args:
            choices_made: The choices presented in the beat just delivered.
            tension: The current dramatic tension or states.
            unresolved_threads: Narrative loose ends or unpursued leads.

        Returns:
            Updated arc dict.
        """
        arc = self.variables.get(self._STORY_ARC_KEY)
        if not isinstance(arc, dict):
            arc = {
                "act": "setup",
                "tension": "",
                "turn_count": 0,
                "unresolved_threads": [],
            }

        arc["turn_count"] = int(arc.get("turn_count", 0)) + 1
        current_act = str(arc.get("act", "setup"))
        threshold = self._ARC_THRESHOLDS.get(current_act)
        if threshold is not None and arc["turn_count"] >= threshold:
            current_idx = self._ARC_PROGRESSION.index(current_act) if current_act in self._ARC_PROGRESSION else 0
            next_idx = min(current_idx + 1, len(self._ARC_PROGRESSION) - 1)
            arc["act"] = self._ARC_PROGRESSION[next_idx]
            logger.debug(
                "Story arc advanced: %s → %s at turn %s",
                current_act, arc["act"], arc["turn_count"],
            )

        if tension is not None:
            arc["tension"] = tension
        if unresolved_threads is not None:
            arc["unresolved_threads"] = unresolved_threads

        self.variables[self._STORY_ARC_KEY] = arc
        self._invalidate_cache()
        return dict(arc)

