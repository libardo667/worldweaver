"""Schemas for the authoritative event reducer and rulebook."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

from ...models.schemas import ActionDeltaContract, ActionFactAppendOperation, StructuredCharacterState


class IntentBase(BaseModel):
    """Base class for all reducer intents."""

    intent_type: str


class ChoiceSelectedIntent(IntentBase):
    """Intent for a player selecting a discrete choice."""

    intent_type: Literal["choice_selected"] = "choice_selected"
    label: str
    delta: ActionDeltaContract


class FreeformActionCommittedIntent(IntentBase):
    """Intent for a player typing a freeform action that was interpreted and validated."""

    intent_type: Literal["freeform_action_committed"] = "freeform_action_committed"
    action_text: str
    delta: ActionDeltaContract


class SystemTickIntent(IntentBase):
    """Intent for an automatic system or environmental turn transition."""

    intent_type: Literal["system_tick"] = "system_tick"


class SimulationTickIntent(IntentBase):
    """Intent representing the aggregated contract of state changes pushed by background subsystems."""

    intent_type: Literal["simulation_tick"] = "simulation_tick"
    delta: ActionDeltaContract


# Union of all possible event intents to funnel through the reducer
EventIntent = Union[ChoiceSelectedIntent, FreeformActionCommittedIntent, SystemTickIntent, SimulationTickIntent]


class ReducerReceipt(BaseModel):
    """Record of exactly what the reducer applied vs rejected."""

    proposed_changes: Dict[str, Any] = Field(default_factory=dict)
    applied_changes: Dict[str, Any] = Field(default_factory=dict)
    rejected_changes: List[str] = Field(default_factory=list)
    rejection_reasons: Dict[str, str] = Field(default_factory=dict)

    # Track discrete stats
    facts_decayed: List[str] = Field(default_factory=list)

    # Canonical facts written to the world graph by this reducer pass (audit trail)
    facts_written: List[ActionFactAppendOperation] = Field(default_factory=list)


# Centralized schema defining numeric clamp boundaries for core state fields.
VARIABLE_CLAMP_SCHEMA: Dict[str, tuple[float, float]] = {
    "tension": (0.0, 10.0),
    "environment.danger_level": (0.0, 10.0),
    "fear": (0.0, 100.0),
    "trust": (0.0, 100.0),
}


STRUCTURED_STANCE_KEY = "stance"
STRUCTURED_FOCUS_KEY = "focus"
STRUCTURED_TACTICS_KEY = "tactics"
STRUCTURED_INJURY_STATE_KEY = "injury_state"
STRUCTURED_STATE_KEYS = frozenset(
    {
        STRUCTURED_STANCE_KEY,
        STRUCTURED_FOCUS_KEY,
        STRUCTURED_TACTICS_KEY,
        STRUCTURED_INJURY_STATE_KEY,
    }
)
UNSTRUCTURED_STATE_BAG_KEY = "state.unstructured"
MAX_UNSTRUCTURED_STATE_ITEMS = 50
MULTI_ACTOR_SCENE_KEYS = ("scene.multi_actor", "scene_state.multi_actor")
STRUCTURED_STATE_HINT_TOKENS = ("stance", "focus", "tactic", "injury")

ALLOWED_STANCES = frozenset({"observing", "hiding", "negotiating", "fleeing", "fighting"})
ALLOWED_INJURY_STATES = frozenset({"healthy", "injured", "critical"})

LEGACY_STANCE_KEY_ALIASES = {
    "is_observing": "observing",
    "observing": "observing",
    "is_hiding": "hiding",
    "hiding": "hiding",
    "is_negotiating": "negotiating",
    "negotiating": "negotiating",
    "is_fleeing": "fleeing",
    "fleeing": "fleeing",
    "is_fighting": "fighting",
    "fighting": "fighting",
}

LEGACY_INJURY_KEY_ALIASES = {
    "is_healthy": "healthy",
    "healthy": "healthy",
    "is_injured": "injured",
    "injured": "injured",
    "is_critical": "critical",
    "critical": "critical",
}

LEGACY_FOCUS_KEY_ALIASES = {"goal_focus", "active_goal", "intent", "target"}


def canonicalize_structured_key(raw_key: str) -> str:
    """Map legacy player-state aliases into canonical structured keys."""
    key = str(raw_key or "").strip().lower()
    if key.startswith("state."):
        suffix = key.split(".", 1)[1].strip()
        if suffix in STRUCTURED_STATE_KEYS:
            return suffix
    if key in LEGACY_STANCE_KEY_ALIASES:
        return STRUCTURED_STANCE_KEY
    if key in LEGACY_INJURY_KEY_ALIASES:
        return STRUCTURED_INJURY_STATE_KEY
    if key in LEGACY_FOCUS_KEY_ALIASES:
        return STRUCTURED_FOCUS_KEY
    return key


def extract_structured_alias_value(raw_key: str, raw_value: Any) -> Any:
    """Resolve a legacy key + value into canonical structured value semantics."""
    key = str(raw_key or "").strip().lower()
    if key in LEGACY_STANCE_KEY_ALIASES:
        stance = LEGACY_STANCE_KEY_ALIASES[key]
        if isinstance(raw_value, bool):
            return stance if raw_value else "observing"
        return raw_value

    if key in LEGACY_INJURY_KEY_ALIASES:
        injury = LEGACY_INJURY_KEY_ALIASES[key]
        if isinstance(raw_value, bool):
            return injury if raw_value else "healthy"
        return raw_value

    if key in LEGACY_FOCUS_KEY_ALIASES:
        return str(raw_value or "").strip()
    return raw_value


def is_structured_state_key(key: str) -> bool:
    return str(key or "").strip().lower() in STRUCTURED_STATE_KEYS


def is_unstructured_state_hint_key(key: str) -> bool:
    lowered = str(key or "").strip().lower()
    if not lowered:
        return False
    if lowered.startswith("state."):
        return canonicalize_structured_key(lowered) not in STRUCTURED_STATE_KEYS
    return any(token in lowered for token in STRUCTURED_STATE_HINT_TOKENS) and not is_structured_state_key(lowered)


def normalize_structured_value(key: str, value: Any) -> tuple[Any, Optional[str]]:
    """Validate and normalize one structured state key/value pair."""
    lowered = str(key or "").strip().lower()

    if lowered == STRUCTURED_STANCE_KEY:
        stance = str(value or "").strip().lower()
        if stance not in ALLOWED_STANCES:
            return None, ("Invalid stance; expected one of " + ", ".join(sorted(ALLOWED_STANCES)))
        return stance, None

    if lowered == STRUCTURED_FOCUS_KEY:
        normalized_focus = StructuredCharacterState(focus=value).focus
        return normalized_focus, None

    if lowered == STRUCTURED_TACTICS_KEY:
        try:
            structured = StructuredCharacterState(tactics=value)
        except Exception:
            return None, "Invalid tactics payload; expected short bounded entries with ttl"
        return [entry.model_dump() for entry in structured.tactics], None

    if lowered == STRUCTURED_INJURY_STATE_KEY:
        injury_state = str(value or "").strip().lower()
        if injury_state not in ALLOWED_INJURY_STATES:
            return None, ("Invalid injury_state; expected one of " + ", ".join(sorted(ALLOWED_INJURY_STATES)))
        return injury_state, None

    return value, None
