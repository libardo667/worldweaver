"""Pydantic models for API schemas."""

import re
from typing import Annotated, Any, Dict, List, Literal, Optional
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

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
    choice_taken: Optional["ActionDeltaContract"] = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "smoke-next",
                "vars": {
                    "name": "Adventurer",
                    "location": "start",
                    "danger": 1,
                },
            }
        }
    )


class ChoiceOut(BaseModel):
    """Response model for storylet choices."""

    label: str
    set: Dict[str, Any] = {}


class NextResp(BaseModel):
    """Response model for next storylet."""

    text: str
    choices: List[ChoiceOut]
    vars: Dict[str, Any]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "You arrive at the lantern-lit crossroads as rain begins to fall.",
                "choices": [
                    {
                        "label": "Head north toward the bridge",
                        "set": {"location": "north_bridge"},
                    },
                    {"label": "Wait and observe", "set": {}},
                ],
                "vars": {
                    "name": "Adventurer",
                    "location": "start",
                    "danger": 1,
                },
            }
        }
    )


class SessionBootstrapRequest(BaseModel):
    """Request model for onboarding-driven world bootstrap."""

    session_id: SessionId
    world_theme: str = Field(..., min_length=1, max_length=120)
    player_role: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=5000)
    key_elements: List[str] = Field(default_factory=list)
    tone: str = Field(default="adventure", min_length=1, max_length=120)
    storylet_count: int = Field(default=15, ge=5, le=50)
    bootstrap_source: str = Field(default="onboarding", min_length=1, max_length=40)


class SessionBootstrapResponse(BaseModel):
    """Response model for session bootstrap endpoint."""

    success: bool = True
    message: str
    session_id: SessionId
    vars: Dict[str, Any] = Field(default_factory=dict)
    storylets_created: int = 0
    theme: str
    player_role: str
    bootstrap_state: str = "completed"


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


class SpatialDirectionTarget(BaseModel):
    """Directional target metadata for compass affordances."""

    id: Optional[int] = None
    title: Optional[str] = None
    text: Optional[str] = None
    requires: Dict[str, Any] = Field(default_factory=dict)
    symbol: Optional[str] = None
    position: Optional[SpatialPosition] = None
    accessible: bool = False
    reason: Optional[str] = None


class SpatialNavigationResponse(BaseModel):
    """Response model for spatial navigation lookup."""

    position: SpatialPosition
    directions: List[str]
    available_directions: Dict[str, Optional[SpatialDirectionTarget]] = Field(default_factory=dict)
    location_storylet: Optional[SpatialStoryletSummary] = None
    leads: List[Dict[str, Any]] = Field(default_factory=list)
    semantic_goal: Optional[str] = None
    goal_hint: Optional[str] = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "position": {"x": 0, "y": 0},
                "directions": ["north", "east", "south"],
                "available_directions": {
                    "north": {
                        "id": 2,
                        "title": "Collapsed Span",
                        "position": {"x": 0, "y": -1},
                        "accessible": False,
                        "reason": "Requirements not met",
                    },
                    "east": {
                        "id": 3,
                        "title": "Ironwright Alley",
                        "position": {"x": 1, "y": 0},
                        "accessible": True,
                    },
                },
                "location_storylet": {
                    "id": 1,
                    "title": "Crossroads Watch",
                    "position": {"x": 0, "y": 0},
                },
                "leads": [
                    {
                        "direction": "north",
                        "storylet_id": 2,
                        "title": "Collapsed Span",
                        "distance": 1.0,
                        "score": 0.81,
                    }
                ],
                "semantic_goal": "find the blacksmith",
                "goal_hint": "You hear hammering to the east.",
            }
        }
    )


class SpatialMoveResponse(BaseModel):
    """Response model for movement operations."""

    result: str
    new_position: SpatialPosition
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "result": "Moved east to Ironwright Alley",
                "new_position": {"x": 1, "y": 0},
            }
        }
    )


class SpatialMapResponse(BaseModel):
    """Response model for full spatial map retrieval."""

    storylets: List[SpatialStoryletSummary]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "storylets": [
                    {
                        "id": 1,
                        "title": "Crossroads Watch",
                        "position": {"x": 0, "y": 0},
                    },
                    {
                        "id": 2,
                        "title": "Collapsed Span",
                        "position": {"x": 0, "y": -1},
                    },
                ]
            }
        }
    )


class SpatialAssignItem(BaseModel):
    """Single assigned storylet position."""

    storylet_id: int
    x: int
    y: int


class SpatialAssignResponse(BaseModel):
    """Response model for bulk spatial assignment."""

    assigned: List[SpatialAssignItem]
    assigned_count: int
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assigned": [
                    {"storylet_id": 1, "x": 0, "y": 0},
                    {"storylet_id": 2, "x": 1, "y": 0},
                ],
                "assigned_count": 2,
            }
        }
    )


class ConstellationEdgesOut(BaseModel):
    """Lightweight semantic + spatial edges for one storylet."""

    spatial_neighbors: Dict[str, int] = Field(default_factory=dict)
    semantic_neighbors: List[int] = Field(default_factory=list)


class ConstellationStoryletOut(BaseModel):
    """Scored storylet payload in semantic constellation responses."""

    id: int
    title: str
    position: Optional[SpatialPosition] = None
    score: float
    accessible: bool
    location: Optional[str] = None
    distance: Optional[float] = None
    edges: ConstellationEdgesOut = Field(default_factory=ConstellationEdgesOut)


class ConstellationContextOut(BaseModel):
    """Current player context summary for constellation debug views."""

    location: str
    vars: Dict[str, Any] = Field(default_factory=dict)


class SemanticConstellationResponse(BaseModel):
    """Response model for semantic constellation debug endpoint."""

    session_id: str
    context: ConstellationContextOut
    storylets: List[ConstellationStoryletOut] = Field(default_factory=list)
    count: int
    top_n: int


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
    filters: Dict[str, str] = Field(default_factory=dict)


class WorldFactsResponse(BaseModel):
    """Response model for world facts query endpoint."""

    query: str
    facts: List[WorldEventOut]
    count: int


class WorldGraphNodeOut(BaseModel):
    """Graph node payload."""

    id: int
    node_type: str
    name: str
    normalized_name: str


class WorldGraphEdgeOut(BaseModel):
    """Graph edge payload."""

    id: int
    edge_type: str
    source_node: WorldGraphNodeOut
    target_node: WorldGraphNodeOut
    weight: float = 1.0
    confidence: float = 0.0
    source_event_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldGraphFactOut(BaseModel):
    """Graph fact/assertion payload."""

    id: int
    session_id: Optional[str] = None
    subject_node: WorldGraphNodeOut
    location_node: Optional[WorldGraphNodeOut] = None
    predicate: str
    value: Any
    confidence: float = 0.0
    is_active: bool = True
    source_event_id: Optional[int] = None
    summary: str
    updated_at: Optional[str] = None


class WorldGraphFactsResponse(BaseModel):
    """Semantic query response over graph facts."""

    query: str
    facts: List[WorldGraphFactOut] = Field(default_factory=list)
    count: int


class WorldGraphNeighborhoodResponse(BaseModel):
    """Neighborhood response for a node in the world graph."""

    node: Optional[WorldGraphNodeOut] = None
    edges: List[WorldGraphEdgeOut] = Field(default_factory=list)
    facts: List[WorldGraphFactOut] = Field(default_factory=list)
    count: int


class WorldLocationFactsResponse(BaseModel):
    """Location-scoped world fact response."""

    location: str
    facts: List[WorldGraphFactOut] = Field(default_factory=list)
    count: int


class WorldProjectionEntryOut(BaseModel):
    """Single world projection row."""

    path: str
    value: Any = None
    is_deleted: bool = False
    confidence: float = 1.0
    source_event_id: Optional[int] = None
    source_event_type: Optional[str] = None
    source_event_summary: Optional[str] = None
    source_event_created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorldProjectionResponse(BaseModel):
    """World projection diagnostic response."""

    prefix: Optional[str] = None
    entries: List[WorldProjectionEntryOut] = Field(default_factory=list)
    count: int


class PrefetchTriggerRequest(BaseModel):
    """Request model for scheduling one session frontier prefetch."""

    session_id: SessionId


class PrefetchTriggerResponse(BaseModel):
    """Response model for prefetch scheduling endpoint."""

    triggered: bool


class PrefetchStatusResponse(BaseModel):
    """Response model for cached frontier status."""

    stubs_cached: int = Field(default=0, ge=0)
    expires_in_seconds: int = Field(default=0, ge=0)


class ActionDeltaSetOperation(BaseModel):
    """Typed set operation for action deltas."""

    key: str = Field(..., min_length=1, max_length=64)
    value: Any


class ActionDeltaIncrementOperation(BaseModel):
    """Typed increment operation for action deltas."""

    key: str = Field(..., min_length=1, max_length=64)
    amount: float


class ActionFactAppendOperation(BaseModel):
    """Optional fact assertion operation emitted by action interpretation."""

    subject: str = Field(..., min_length=1, max_length=120)
    predicate: str = Field(..., min_length=1, max_length=120)
    value: Any
    location: Optional[str] = Field(default=None, max_length=120)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class ActionDeltaContract(BaseModel):
    """Strict action delta contract with typed operations."""

    set: List[ActionDeltaSetOperation] = Field(default_factory=list)
    increment: List[ActionDeltaIncrementOperation] = Field(default_factory=list)
    append_fact: List[ActionFactAppendOperation] = Field(default_factory=list)


class ActionReasoningMetadata(BaseModel):
    """Persisted reasoning metadata for interpreted freeform actions."""

    facts_considered: List[str] = Field(default_factory=list)
    rejected_keys: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    contradiction: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    rationale: Optional[str] = None
    goal_update: Optional[Dict[str, Any]] = None
    appended_facts: List[ActionFactAppendOperation] = Field(default_factory=list)
    suggested_beats: List[Dict[str, Any]] = Field(default_factory=list)


class ActionRequest(BaseModel):
    """Request model for freeform player action."""

    session_id: SessionId
    action: str = Field(..., min_length=1, max_length=2000)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "smoke-action",
                "action": "I inspect the broken bridge supports for weak points.",
                "idempotency_key": "action-smoke-001",
            }
        }
    )

    @field_validator("idempotency_key")
    @classmethod
    def _validate_idempotency_key(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if not re.match(r"^[a-zA-Z0-9._:-]{1,128}$", cleaned):
            raise ValueError(
                "idempotency_key must use only letters, digits, dot, underscore, colon, or hyphen"
            )
        return cleaned


class ActionChoice(BaseModel):
    """A follow-up choice suggested after an action."""

    label: str
    set: Dict[str, Any] = {}


class ActionResponse(BaseModel):
    """Response model for interpreted player action."""

    narrative: str
    ack_line: Optional[str] = None
    state_changes: Dict[str, Any] = {}
    choices: List[ActionChoice] = []
    plausible: bool = True
    vars: Dict[str, Any] = {}
    triggered_storylet: Optional[str] = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "narrative": "You test the beams and find rot near the eastern support.",
                "state_changes": {
                    "environment": {"bridge_stability": "fragile"},
                },
                "choices": [
                    {
                        "label": "Reinforce the support",
                        "set": {"intent": "repair_bridge"},
                    },
                    {
                        "label": "Warn nearby travelers",
                        "set": {"intent": "warn_travelers"},
                    },
                ],
                "plausible": True,
                "vars": {"location": "old_bridge", "danger": 3},
                "triggered_storylet": "A sentry notices your caution and approaches.",
            }
        }
    )


class TurnRequest(BaseModel):
    """Unified turn request for optional /api/turn endpoint."""

    session_id: SessionId
    turn_type: Literal["next", "action"] = "next"
    vars: Dict[str, Any] = Field(default_factory=dict)
    choice_taken: Optional[ActionDeltaContract] = None
    action: Optional[str] = Field(default=None, max_length=2000)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "turn-smoke",
                "turn_type": "action",
                "action": "I inspect the gate hinges.",
                "idempotency_key": "turn-smoke-001",
            }
        }
    )

    @field_validator("idempotency_key")
    @classmethod
    def _validate_turn_idempotency_key(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if not re.match(r"^[a-zA-Z0-9._:-]{1,128}$", cleaned):
            raise ValueError(
                "idempotency_key must use only letters, digits, dot, underscore, colon, or hyphen"
            )
        return cleaned


class TurnResponse(BaseModel):
    """Unified turn response for optional /api/turn endpoint."""

    turn_type: Literal["next", "action"]
    next: Optional[NextResp] = None
    action: Optional[ActionResponse] = None


class AuthorPhaseReceipt(BaseModel):
    """Phase-level execution receipt for author mutation workflows."""

    name: str
    status: Literal["started", "completed", "failed"]
    started_at: str
    completed_at: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class AuthorOperationReceipt(BaseModel):
    """Operation-level execution receipt for author generation workflows."""

    operation: str
    status: Literal["started", "completed", "completed_with_warnings", "failed"]
    started_at: str
    completed_at: Optional[str] = None
    counts: Dict[str, int] = Field(default_factory=dict)
    phases: List[AuthorPhaseReceipt] = Field(default_factory=list)
    rollback_actions: List[Dict[str, Any]] = Field(default_factory=list)


class GoalUpdateRequest(BaseModel):
    """Request model for creating or updating a session goal state."""

    primary_goal: Optional[str] = Field(default=None, min_length=1, max_length=300)
    subgoals: Optional[List[str]] = Field(default=None)
    urgency: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    complication: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    note: Optional[str] = Field(default=None, max_length=300)

    @field_validator("subgoals")
    @classmethod
    def _validate_subgoals(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned[:10]


class GoalMilestoneRequest(BaseModel):
    """Request model for appending a goal milestone / arc event."""

    title: str = Field(..., min_length=1, max_length=300)
    status: Literal[
        "progressed",
        "complicated",
        "derailed",
        "branched",
        "completed",
    ] = "progressed"
    note: Optional[str] = Field(default=None, max_length=300)
    urgency_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    complication_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
