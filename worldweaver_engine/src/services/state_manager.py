# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""
Advanced State Management System for WorldWeaver

This module provides sophisticated state tracking capabilities inspired by
successful Twine games like "The Play" (relationships), "Hallowmoor" (inventory),
and environmental storytelling techniques.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta, timezone
from collections import deque
from dataclasses import dataclass
import logging

from ..models.schemas import StructuredCharacterState
from .requirements import evaluate_requirement_value, evaluate_requirements
from .state import (
    InventoryDomain,
    ItemState,
    RelationshipDomain,
    RelationshipState,
    StateChange,
    StateChangeType,
)

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


# StateChangeType, StateChange, ItemState, and RelationshipState
# are now canonical in src/services/state/. Imported above for use throughout this module.
# Compat re-exports preserved for callers that imported directly from state_manager.
# Retirement condition: after Major 106, verify no external code imports these from here.


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
        self._inventory = InventoryDomain()
        self._relationships = RelationshipDomain()
        self.environment = EnvironmentalState()
        self.change_history = deque(maxlen=200)
        self.context_stack = []

        # Performance optimization: cache frequently accessed computations
        self._cached_computations = {}
        self._cache_expiry = datetime.now(timezone.utc)
        self.ensure_structured_state_defaults(record_history=False)

    # ------------------------------------------------------------------
    # Backward-compatible property facades (preserve direct attribute access
    # across all 7 caller files without modifying them).
    # ------------------------------------------------------------------

    @property
    def inventory(self) -> Dict[str, ItemState]:
        """Direct reference to the inventory items dict."""
        return self._inventory.items

    @property
    def relationships(self) -> Dict[str, RelationshipState]:
        """Direct reference to the relationships items dict."""
        return self._relationships.items

    def set_variable(
        self,
        key: str,
        value: Any,
        context: Optional[Dict[str, Any]] = None,
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

    def delete_variable(
        self,
        key: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Delete a variable and record the removal."""
        if key not in self.variables:
            return False

        old_value = self.variables[key]
        change = StateChange(
            change_type=StateChangeType.REMOVE,
            variable=key,
            old_value=old_value,
            new_value=None,
            context=context or {},
        )
        self.change_history.append(change)

        del self.variables[key]
        self._invalidate_cache()
        logger.debug(f"Variable '{key}' deleted")
        return True

    def increment_variable(
        self,
        key: str,
        amount: Union[int, float] = 1,
        context: Optional[Dict[str, Any]] = None,
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
        )
        self.change_history.append(change)

        self.variables[key] = new_value
        self._invalidate_cache()
        return new_value

    def ensure_structured_state_defaults(self, *, record_history: bool = False) -> None:
        """Ensure canonical structured state fields are present and normalized."""
        if not isinstance(self.variables, dict):
            self.variables = {}

        changed = False
        defaults = StructuredCharacterState().model_dump()
        payload = {
            "stance": self.variables.get("stance", defaults["stance"]),
            "focus": self.variables.get("focus", defaults["focus"]),
            "tactics": self.variables.get("tactics", defaults["tactics"]),
            "injury_state": self.variables.get("injury_state", defaults["injury_state"]),
        }
        try:
            structured = StructuredCharacterState.model_validate(payload).model_dump()
        except Exception:
            structured = defaults

        for key, value in structured.items():
            if self.variables.get(key) == value:
                continue
            changed = True
            if record_history:
                self.set_variable(key, value)
            else:
                self.variables[key] = value

        bag_key = "state.unstructured"
        if not isinstance(self.variables.get(bag_key), dict):
            changed = True
            if record_history:
                self.set_variable(bag_key, {})
            else:
                self.variables[bag_key] = {}

        if changed and not record_history:
            self._invalidate_cache()

    def get_unstructured_state_bag(self) -> Dict[str, Any]:
        """Return a copy of namespaced non-canonical state fields."""
        self.ensure_structured_state_defaults(record_history=False)
        bag = self.variables.get("state.unstructured", {})
        return dict(bag) if isinstance(bag, dict) else {}

    def set_unstructured_state_value(
        self,
        key: str,
        value: Any,
        *,
        max_items: int = 50,
    ) -> Dict[str, Any]:
        """Shunt one unrecognized key into the namespaced unstructured bag."""
        self.ensure_structured_state_defaults(record_history=False)
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return self.get_unstructured_state_bag()

        bag = self.get_unstructured_state_bag()
        bag[normalized_key] = value
        while len(bag) > max(1, int(max_items)):
            oldest = next(iter(bag))
            bag.pop(oldest, None)
        self.set_variable("state.unstructured", bag)
        return dict(bag)

    def decay_tactics(self) -> List[str]:
        """Decrement tactic TTL by one turn and return expired tactic names."""
        self.ensure_structured_state_defaults(record_history=False)
        tactics_payload = {"tactics": self.variables.get("tactics", [])}
        try:
            active = StructuredCharacterState.model_validate(tactics_payload).tactics
        except Exception:
            self.set_variable("tactics", [])
            return []

        updated: List[Dict[str, Any]] = []
        expired: List[str] = []
        for tactic in active:
            next_ttl = int(tactic.ttl) - 1
            if next_ttl <= 0:
                expired.append(tactic.name)
                continue
            updated.append({"name": tactic.name, "ttl": next_ttl})

        if updated != tactics_payload["tactics"]:
            self.set_variable("tactics", updated)
        return expired

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
            item = ItemState(id=item_id, name=name, quantity=quantity, properties=properties or {})
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
                new_value = max(-100, min(100, current_value + change_amount))  # Clamp to -100/100
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

    def get_relationship(self, entity_a: str, entity_b: str) -> Optional[RelationshipState]:
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
            filtered = {key: value for key, value in env_changes.items() if hasattr(self.environment, key)}
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
                if not isinstance(requirements, dict):
                    logger.warning("evaluate_condition: malformed relationship requirement for %r (got %r); skipping", key, requirements)
                    continue
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
                if not isinstance(requirements, dict):
                    logger.warning("evaluate_condition: malformed item requirement for %r (got %r); skipping", key, requirements)
                    continue
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
                if not isinstance(requirements, dict):
                    logger.warning("evaluate_condition: malformed environment requirement (got %r); skipping", requirements)
                    continue
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
        self.ensure_structured_state_defaults(record_history=False)
        cache_key = "contextual_vars"
        if cache_key in self._cached_computations and datetime.now(timezone.utc) < self._cache_expiry:
            return self._cached_computations[cache_key]

        # Base variables
        context: Dict[str, Any] = dict(self.variables)

        # Add computed values
        context["_inventory_count"] = len(self.inventory)
        context["_total_item_quantity"] = sum(item.quantity for item in self.inventory.values())
        context["_relationship_count"] = len(self.relationships)
        context["_time_of_day"] = self.environment.time_of_day
        context["_weather"] = self.environment.weather
        context["_danger_level"] = self.environment.danger_level

        # Add non-underscore versions for compatibility
        context["inventory_count"] = len(self.inventory)
        context["total_item_quantity"] = sum(item.quantity for item in self.inventory.values())
        context["relationship_count"] = len(self.relationships)
        context["time_of_day"] = self.environment.time_of_day
        context["weather"] = self.environment.weather
        context["danger_level"] = self.environment.danger_level
        context["inventory_items"] = list(self.inventory.keys())
        context["known_people"] = list({rel.entity_a if rel.entity_a != "player" else rel.entity_b for rel in self.relationships.values()})
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
        self.ensure_structured_state_defaults(record_history=False)
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
            "recent_changes": len([c for c in self.change_history if c.timestamp > datetime.now(timezone.utc) - timedelta(minutes=5)]),
        }

    def fork_for_projection(self) -> "AdvancedStateManager":
        """Create a lightweight copy for speculative projection.

        Returns a new AdvancedStateManager with a shallow copy of variables
        and shared (read-only) references to inventory, relationships, etc.
        The fork is marked ``_is_projection_fork = True`` to prevent
        accidental persistence.
        """
        fork = AdvancedStateManager.__new__(AdvancedStateManager)
        fork.session_id = self.session_id
        fork.variables = self.variables.copy()
        # Shared read-only domain references — projection never mutates these
        fork._inventory = self._inventory
        fork._relationships = self._relationships
        fork.environment = self.environment
        fork.change_history = deque(maxlen=0)
        fork.context_stack = []
        fork._cached_computations = {}
        fork._cache_expiry = datetime.now(timezone.utc)
        fork._is_projection_fork = True
        return fork

    def export_state(self) -> Dict[str, Any]:
        """Export complete state as a JSON-serializable dict.

        Returns a v2 payload that includes inventory, relationships, and
        environment — not just flat variables.  All datetime values are
        converted to ISO-format strings so the result can be stored directly
        in the JSON column of SessionVars.  change_history is intentionally
        omitted because old_value/new_value can hold arbitrary objects.
        """
        self.ensure_structured_state_defaults(record_history=False)

        return {
            "_v": 2,
            "session_id": self.session_id,
            "variables": self.variables,
            "inventory": self._inventory.to_dict(),
            "relationships": self._relationships.to_dict(),
            "environment": self.environment.__dict__.copy(),
        }

    def import_state(self, state_data: Dict[str, Any]):
        """Import state from a v2 export_state() payload.

        Handles datetime strings produced by export_state() and is safe to
        call with an empty or partial payload (missing keys default to their
        initial values).
        """
        self.session_id = state_data.get("session_id", self.session_id)
        self.variables = state_data.get("variables", {})
        if not isinstance(self.variables, dict):
            self.variables = {}

        # Reconstruct typed domains from their serialized sections.
        self._inventory = InventoryDomain.from_dict(state_data.get("inventory", {}))
        self._relationships = RelationshipDomain.from_dict(state_data.get("relationships", {}))

        # Reconstruct environment.
        if "environment" in state_data:
            self.environment = EnvironmentalState(**state_data["environment"])

        # change_history is not persisted (v2 omits it intentionally).
        self.change_history = deque(maxlen=200)
        self.ensure_structured_state_defaults(record_history=False)

        self._invalidate_cache()
        logger.info(f"Imported state for session {self.session_id}")

    # -----------------------------------------------------------------------
    # Shared world identity and context helpers
    # -----------------------------------------------------------------------

    _WORLD_CONTEXT_KEY = "_world_context"
    _WORLD_ID_KEY = "_world_id"

    def set_world_context(self, context: Dict[str, Any]) -> None:
        """Persist a thin shared-world context object into session state."""
        if not isinstance(context, dict):
            raise TypeError(f"world_context must be a dict, got {type(context).__name__}")
        self.variables[self._WORLD_CONTEXT_KEY] = context
        self._invalidate_cache()
        logger.debug("World context stored for session %s", self.session_id)

    def get_world_context(self) -> Optional[Dict[str, Any]]:
        """Return the stored world context header, or None if absent."""
        value = self.variables.get(self._WORLD_CONTEXT_KEY)
        return value if isinstance(value, dict) else None

    def get_world_id(self) -> Optional[str]:
        """Return the shared world_id if this is a resident session, else None."""
        v = self.variables.get(self._WORLD_ID_KEY)
        return str(v) if v else None

    def set_world_id(self, world_id: str) -> None:
        """Link this resident session to a shared world."""
        self.variables[self._WORLD_ID_KEY] = str(world_id)
        self._invalidate_cache()
        logger.debug("Session %s linked to world %s", self.session_id, world_id)

    def effective_world_session_id(self) -> str:
        """Returns the world_id if this is a resident session, else own session_id.

        Use this everywhere you want to scope events/history to the shared world
        rather than the individual resident.
        """
        return self.get_world_id() or self.session_id
