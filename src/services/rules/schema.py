"""Schemas for the authoritative event reducer and rulebook."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

from ...models.schemas import ActionDeltaContract


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


# Union of all possible event intents to funnel through the reducer
EventIntent = Union[ChoiceSelectedIntent, FreeformActionCommittedIntent, SystemTickIntent]


class ReducerReceipt(BaseModel):
    """Record of exactly what the reducer applied vs rejected."""
    
    proposed_changes: Dict[str, Any] = Field(default_factory=dict)
    applied_changes: Dict[str, Any] = Field(default_factory=dict)
    rejected_changes: List[str] = Field(default_factory=list)
    rejection_reasons: Dict[str, str] = Field(default_factory=dict)
    
    # Track discrete stats
    facts_decayed: List[str] = Field(default_factory=list)
