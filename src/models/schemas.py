"""Pydantic models for API schemas."""

import re
from typing import Annotated, Any, Dict, List, Optional
from pydantic import AfterValidator, BaseModel, Field, field_validator

_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_session_id(v: str) -> str:
    if not 1 <= len(v) <= 128:
        raise ValueError("session_id must be 1-128 characters")
    if not _SESSION_ID_RE.match(v):
        raise ValueError("session_id must contain only alphanumeric, hyphen, or underscore characters")
    return v


SessionId = Annotated[str, AfterValidator(_validate_session_id)]


class NextReq(BaseModel):
    """Request model for getting next storylet."""

    session_id: SessionId
    vars: Dict[str, Any]


class ChoiceOut(BaseModel):
    """Response model for storylet choices."""

    label: str
    set: Dict[str, Any] = {}


class NextResp(BaseModel):
    """Response model for next storylet."""

    text: str
    choices: List[ChoiceOut]
    vars: Dict[str, Any]


class StoryletIn(BaseModel):
    """Input model for creating storylets."""

    title: str = Field(..., max_length=200)
    text_template: str
    requires: Dict[str, Any] = Field(default_factory=dict)
    choices: List[Dict[str, Any]] = Field(default_factory=list)
    weight: float = 1.0
    position: Dict[str, int] = Field(default_factory=lambda: {"x": 0, "y": 0}, description="Position for spatial navigation")

    # Accept both {"label", "set"} and {"text", "set_vars"}; normalize to label/set
    @field_validator("choices", mode="before")
    @classmethod
    def _normalize_choices(cls, v):
        out = []
        for c in v or []:
            label = c.get("label") or c.get("text") or "Continue"
            set_obj = c.get("set") or c.get("set_vars") or {}
            out.append({"label": label, "set": set_obj})
        return out


class SuggestReq(BaseModel):
    """Request model for suggesting storylets."""

    n: int = Field(
        default=3, ge=1, le=20, description="Number of storylets to suggest (1-20)"
    )
    themes: List[str] = Field(default_factory=list)
    bible: Dict[str, Any] = Field(default_factory=dict)


class SuggestResp(BaseModel):
    """Response model for suggested storylets."""

    storylets: List[StoryletIn]


class GenerateStoryletRequest(BaseModel):
    """Request to generate storylets with AI assistance."""

    count: int = Field(
        default=3, ge=1, le=15, description="Number of storylets to generate (1-15)"
    )
    themes: List[str] = Field(default_factory=list, description="Themes to incorporate")
    intelligent: bool = Field(default=True, description="Use intelligent analysis")


class WorldDescription(BaseModel):
    """Request model for generating a complete world from user description."""

    description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Detailed description of your story world",
    )
    theme: str = Field(
        ..., min_length=3, max_length=100, description="Main theme or genre"
    )
    player_role: str = Field(
        default="adventurer", description="What role does the player take?"
    )
    key_elements: List[str] = Field(
        default_factory=list,
        description="Important world elements, locations, or concepts",
    )
    tone: str = Field(
        default="adventure",
        description="Story tone: adventure, horror, comedy, epic, etc.",
    )
    storylet_count: int = Field(
        default=15, ge=5, le=50, description="Number of storylets to generate"
    )
    confirm_delete: bool = Field(
        default=False,
        description=(
            "Must be true to allow replacing all existing storylets during world generation."
        ),
    )


class SpatialPosition(BaseModel):
    """Cartesian position for a storylet on the spatial map."""

    x: int
    y: int


class SpatialStoryletSummary(BaseModel):
    """Minimal storylet details returned by spatial endpoints."""

    id: int
    title: str
    position: SpatialPosition


class SpatialNavigationResponse(BaseModel):
    """Response model for spatial navigation lookup."""

    position: SpatialPosition
    directions: List[str]
    location_storylet: Optional[SpatialStoryletSummary] = None


class SpatialMoveResponse(BaseModel):
    """Response model for movement operations."""

    result: str
    new_position: SpatialPosition


class SpatialMapResponse(BaseModel):
    """Response model for full spatial map retrieval."""

    storylets: List[SpatialStoryletSummary]


class SpatialAssignItem(BaseModel):
    """Single assigned storylet position."""

    storylet_id: int
    x: int
    y: int


class SpatialAssignResponse(BaseModel):
    """Response model for bulk spatial assignment."""

    assigned: List[SpatialAssignItem]
    assigned_count: int


class WorldEventOut(BaseModel):
    """Response model for a single world event."""

    id: int
    session_id: Optional[str] = None
    storylet_id: Optional[int] = None
    event_type: str
    summary: str
    world_state_delta: Dict[str, Any] = {}
    created_at: Optional[str] = None


class WorldHistoryResponse(BaseModel):
    """Response model for world history endpoint."""

    events: List[WorldEventOut]
    count: int


class WorldFactsResponse(BaseModel):
    """Response model for world facts query endpoint."""

    query: str
    facts: List[WorldEventOut]
    count: int


class ActionRequest(BaseModel):
    """Request model for freeform player action."""

    session_id: SessionId
    action: str = Field(..., min_length=1, max_length=2000)


class ActionChoice(BaseModel):
    """A follow-up choice suggested after an action."""

    label: str
    set: Dict[str, Any] = {}


class ActionResponse(BaseModel):
    """Response model for interpreted player action."""

    narrative: str
    state_changes: Dict[str, Any] = {}
    choices: List[ActionChoice] = []
    plausible: bool = True
    vars: Dict[str, Any] = {}
    triggered_storylet: Optional[str] = None
