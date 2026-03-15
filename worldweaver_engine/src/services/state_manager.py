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
import re

from ..models import NarrativeBeat
from ..models.schemas import StructuredCharacterState
from .requirements import evaluate_requirement_value, evaluate_requirements
from .state import (
    InventoryDomain,
    ItemState,
    RelationshipDomain,
    RelationshipState,
    GoalDomain,
    GoalMilestone,
    GoalState,
    NarrativeBeatsDomain,
    StateChange,
    StateChangeType,
)

logger = logging.getLogger(__name__)

SCENE_CARD_NOW_KEY = "_scene_card_now"
SCENE_CARD_HISTORY_KEY = "_scene_card_history"
MAX_SCENE_CARD_HISTORY = 40
MOTIF_LEDGER_KEY = "state.recent_motifs"
MAX_MOTIF_LEDGER_ITEMS = 32
MAX_MOTIF_EXTRACT_PER_TEXT = 8
_MOTIF_TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9'-]*")
_MOTIF_STOPWORDS = {
    "about",
    "across",
    "after",
    "again",
    "against",
    "around",
    "before",
    "being",
    "between",
    "beyond",
    "during",
    "from",
    "here",
    "into",
    "just",
    "more",
    "most",
    "near",
    "onto",
    "over",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "under",
    "until",
    "very",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "within",
    "without",
    "would",
}


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


# StateChangeType, StateChange, ItemState, RelationshipState, GoalMilestone, GoalState
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


# GoalMilestone and GoalState now live in src/services/state/goals.py (imported above).


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
        self._goals = GoalDomain()
        self._beats = NarrativeBeatsDomain()
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

    @property
    def goal_state(self) -> GoalState:
        """Direct reference to the GoalState object."""
        return self._goals.state

    @property
    def active_narrative_beats(self) -> List[NarrativeBeat]:
        return self._beats.beats

    @active_narrative_beats.setter
    def active_narrative_beats(self, value: List[NarrativeBeat]) -> None:
        self._beats._beats = value

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

    def delete_variable(
        self,
        key: str,
        context: Optional[Dict[str, Any]] = None,
        storylet_id: Optional[int] = None,
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
            storylet_id=storylet_id,
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

        if not isinstance(self.variables.get(MOTIF_LEDGER_KEY), list):
            changed = True
            if record_history:
                self.set_variable(MOTIF_LEDGER_KEY, [])
            else:
                self.variables[MOTIF_LEDGER_KEY] = []

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

    def persist_scene_card(
        self,
        scene_card: Dict[str, Any],
        *,
        source: str = "turn",
        max_history: int = MAX_SCENE_CARD_HISTORY,
    ) -> Dict[str, Any]:
        """Persist canonical per-turn scene-card state with bounded history."""
        if not isinstance(scene_card, dict):
            scene_card = {}

        now_card = dict(scene_card)
        self.set_variable(SCENE_CARD_NOW_KEY, now_card)

        history_raw = self.get_variable(SCENE_CARD_HISTORY_KEY, [])
        history: List[Dict[str, Any]]
        if isinstance(history_raw, list):
            history = [entry for entry in history_raw if isinstance(entry, dict)]
        else:
            history = []

        history.append(
            {
                "scene_card": now_card,
                "source": str(source or "turn")[:64],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        bounded = max(1, int(max_history))
        if len(history) > bounded:
            history = history[-bounded:]

        self.set_variable(SCENE_CARD_HISTORY_KEY, history)
        return now_card

    def get_scene_card_now(self) -> Dict[str, Any]:
        payload = self.get_variable(SCENE_CARD_NOW_KEY, {})
        return dict(payload) if isinstance(payload, dict) else {}

    def get_scene_card_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        payload = self.get_variable(SCENE_CARD_HISTORY_KEY, [])
        if not isinstance(payload, list):
            return []
        bounded = max(1, int(limit))
        rows = [entry for entry in payload if isinstance(entry, dict)]
        return rows[-bounded:]

    def extract_motifs_from_text(
        self,
        text: str,
        *,
        max_items: int = MAX_MOTIF_EXTRACT_PER_TEXT,
        min_token_length: int = 4,
    ) -> List[str]:
        """Deterministically extract compact motif tokens from narration text."""
        normalized = " ".join(str(text or "").strip().lower().split())
        if not normalized:
            return []

        output: List[str] = []
        seen: set[str] = set()
        limit = max(1, int(max_items))
        token_len = max(2, int(min_token_length))
        for raw_token in _MOTIF_TOKEN_PATTERN.findall(normalized):
            token = raw_token.strip("'")
            if not token:
                continue
            if len(token) < token_len:
                continue
            if token in _MOTIF_STOPWORDS:
                continue
            if token.isdigit():
                continue
            if token in seen:
                continue
            seen.add(token)
            output.append(token)
            if len(output) >= limit:
                break
        return output

    def get_recent_motifs(self, limit: int = MAX_MOTIF_LEDGER_ITEMS) -> List[str]:
        """Return bounded motif ledger from session state."""
        payload = self.get_variable(MOTIF_LEDGER_KEY, [])
        if not isinstance(payload, list):
            return []
        bounded = max(1, int(limit))
        values = [str(item).strip().lower() for item in payload if str(item).strip()]
        return values[-bounded:]

    def append_recent_motifs(
        self,
        motifs: List[str],
        *,
        max_items: int = MAX_MOTIF_LEDGER_ITEMS,
    ) -> List[str]:
        """Append motifs to rolling ledger with dedupe and bounded retention."""
        current = self.get_recent_motifs(limit=max_items)
        merged: List[str] = list(current)
        seen = set(current)
        for raw in motifs:
            motif = str(raw or "").strip().lower()
            if not motif:
                continue
            if motif in seen:
                continue
            seen.add(motif)
            merged.append(motif)

        bounded = max(1, int(max_items))
        if len(merged) > bounded:
            merged = merged[-bounded:]
        self.set_variable(MOTIF_LEDGER_KEY, merged)
        return list(merged)

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
        valid_statuses = {"progressed", "complicated", "derailed", "branched", "completed"}
        clean_status = str(status).lower().strip()
        if clean_status not in valid_statuses:
            clean_status = "progressed"

        milestone = GoalMilestone(
            title=str(title).strip() or "Milestone",
            status=clean_status,
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
            cleaned_subgoals = [str(goal).strip() for goal in subgoals[:10] if str(goal).strip()]
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
        self.goal_state.urgency = self._clamp_goal_signal(self.goal_state.urgency + float(urgency_delta))
        self.goal_state.complication = self._clamp_goal_signal(self.goal_state.complication + float(complication_delta))
        self._record_goal_milestone(
            title=title,
            status=status,
            note=note,
            source=source,
            urgency_delta=urgency_delta,
            complication_delta=complication_delta,
        )
        return self.get_goal_state()

    def get_goal_lens_payload(self) -> Dict[str, Any]:
        """Return the structured goal lens payload for synthesis and semantic matching."""
        milestones = [m.to_dict() for m in self.goal_state.milestones[-3:]]
        return {
            "primary_goal": str(self.goal_state.primary_goal or ""),
            "subgoals": list(self.goal_state.subgoals),
            "urgency": float(self.goal_state.urgency),
            "complication": float(self.goal_state.complication),
            "recent_milestones": milestones,
        }

    def apply_goal_update(
        self,
        update: Dict[str, Any],
        *,
        source: str = "system",
    ) -> Dict[str, Any]:
        """Apply goal changes from action interpretation metadata."""
        if not update:
            return self.get_goal_state()

        status = str(update.get("status", "progressed")).lower()
        valid_statuses = {"progressed", "complicated", "derailed", "branched", "completed"}
        if status not in valid_statuses:
            status = "progressed"

        milestone = str(update.get("milestone", "")).strip()
        note = str(update.get("note", "")).strip()
        subgoal = str(update.get("subgoal", "")).strip()

        urgency_delta = float(update.get("urgency_delta", 0.0))
        complication_delta = float(update.get("complication_delta", 0.0))

        # Apply heuristic deltas if none explicitly provided
        if urgency_delta == 0.0 and complication_delta == 0.0:
            if status == "complicated":
                urgency_delta = 0.1
                complication_delta = 0.2
            elif status == "derailed":
                urgency_delta = 0.2
                complication_delta = 0.4
            elif status == "branched":
                urgency_delta = 0.05
                complication_delta = 0.1
            elif status == "progressed":
                complication_delta = -0.05
            elif status == "completed":
                urgency_delta = -0.2
                complication_delta = -0.1

        primary_goal = update.get("primary_goal")
        if primary_goal is not None:
            self.set_goal_state(
                primary_goal=str(primary_goal),
                source=source,
                note=note,
            )

        if subgoal:
            self.add_goal_subgoal(subgoal, source=source)

        if milestone or urgency_delta or complication_delta:
            self.mark_goal_milestone(
                milestone or "Goal state adjusted",
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
        recent = self.goal_state.milestones[-max(1, int(limit)) :]
        return [milestone.to_dict() for milestone in reversed(recent)]

    def get_goal_embedding_context(self) -> str:
        """Dense text context that can be embedded for semantic scoring."""
        if not self.goal_state.primary_goal:
            return ""

        parts = [f"Primary goal: {self.goal_state.primary_goal}"]
        if self.goal_state.subgoals:
            parts.append("Subgoals: " + ", ".join(self.goal_state.subgoals[:5]))
        parts.append(f"Goal urgency={self.goal_state.urgency:.2f}, complication={self.goal_state.complication:.2f}")
        if self.goal_state.milestones:
            milestone_text = "; ".join(f"{m.status}: {m.title}" for m in self.goal_state.milestones[-3:])
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
        context["goal_primary"] = self.goal_state.primary_goal
        context["goal_subgoals"] = list(self.goal_state.subgoals[:5])

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
        fork._goals = self._goals
        fork._beats = self._beats
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
            "goal_state": self._goals.to_dict(),
            "environment": self.environment.__dict__.copy(),
            "narrative_beats": self._beats.to_dict(),
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

        goal_payload = state_data.get("goal_state", {})
        self._goals = GoalDomain.from_dict(goal_payload if isinstance(goal_payload, dict) else {})

        self._beats = NarrativeBeatsDomain()
        for beat_payload in state_data.get("narrative_beats", []):
            if not isinstance(beat_payload, dict):
                continue
            try:
                self._beats.add(NarrativeBeat.from_dict(beat_payload))
            except Exception:
                continue

        # change_history is not persisted (v2 omits it intentionally).
        self.change_history = deque(maxlen=200)
        self.ensure_structured_state_defaults(record_history=False)

        self._invalidate_cache()
        logger.info(f"Imported state for session {self.session_id}")

    # -----------------------------------------------------------------------
    # JIT BEAT PIPELINE — world bible and story arc helpers
    # -----------------------------------------------------------------------

    _WORLD_BIBLE_KEY = "_world_bible"
    _WORLD_ID_KEY = "_world_id"
    _STORY_ARC_KEY = "_story_arc"
    _GOAL_BACKFILL_NOTE = "auto_backfill_after_initial_turn"
    _GOAL_BACKFILL_SOURCE = "system_goal_backfill"

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

    def get_story_arc(self) -> Dict[str, Any]:
        """Return the current turn counter state, initialising it if absent."""
        arc = self.variables.get(self._STORY_ARC_KEY)
        if not isinstance(arc, dict):
            arc = {"turn_count": 0}
            self.variables[self._STORY_ARC_KEY] = arc
            self._invalidate_cache()
        return dict(arc)

    def _derive_fallback_goal_thesis(self) -> str:
        """Build a deterministic fallback primary-goal thesis."""
        role = ""
        for key in ("player_role", "character_profile", "role", "occupation"):
            candidate = str(self.variables.get(key, "")).strip()
            if candidate:
                role = candidate
                break
        role = role or "wanderer"

        world_theme = str(self.variables.get("world_theme", "")).strip()

        if world_theme:
            return (f"As {role}, establish your footing in this {world_theme} world and secure a reliable way forward.")[:220]
        return f"As {role}, secure your footing and define a clear path forward."[:220]

    def backfill_primary_goal_if_empty_after_initial_turn(
        self,
        *,
        minimum_turn_count: int = 1,
        source: str = _GOAL_BACKFILL_SOURCE,
    ) -> Dict[str, Any]:
        """Populate primary_goal once after turn 1 if still empty.

        This is deterministic and idempotent:
        - no-op when a primary goal already exists,
        - no-op before the configured turn threshold,
        - applies one explicit goal-state update when both conditions are met.
        """
        current_goal = str(self.goal_state.primary_goal or "").strip()
        if current_goal:
            return {
                "applied": False,
                "reason": "primary_goal_present",
                "primary_goal": current_goal,
            }

        arc_payload = self.variables.get(self._STORY_ARC_KEY)
        if isinstance(arc_payload, dict):
            turn_count = max(0, int(arc_payload.get("turn_count", 0) or 0))
        else:
            turn_count = 0
        required = max(1, int(minimum_turn_count))
        if turn_count < required:
            return {
                "applied": False,
                "reason": "below_turn_threshold",
                "turn_count": turn_count,
                "minimum_turn_count": required,
                "primary_goal": "",
            }

        fallback_goal = self._derive_fallback_goal_thesis()
        if not fallback_goal:
            return {
                "applied": False,
                "reason": "fallback_empty",
                "turn_count": turn_count,
                "primary_goal": "",
            }

        self.set_goal_state(
            primary_goal=fallback_goal,
            source=source,
            note=self._GOAL_BACKFILL_NOTE,
        )
        return {
            "applied": True,
            "reason": "goal_backfilled",
            "turn_count": turn_count,
            "primary_goal": str(self.goal_state.primary_goal or ""),
            "source": source,
            "note": self._GOAL_BACKFILL_NOTE,
        }

    def advance_story_arc(
        self,
        choices_made: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Increment turn_count. Drama fields (act/tension/unresolved_threads) removed."""
        arc = self.variables.get(self._STORY_ARC_KEY)
        if not isinstance(arc, dict):
            arc = {"turn_count": 0}
        arc["turn_count"] = int(arc.get("turn_count", 0)) + 1
        self.variables[self._STORY_ARC_KEY] = arc
        self._invalidate_cache()
        return dict(arc)
