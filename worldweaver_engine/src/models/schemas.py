# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Pydantic models for API schemas."""

import re
from typing import Annotated, Any, Dict, List, Literal, Optional
from pydantic import AfterValidator, BaseModel, Field, field_validator

_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_TACTIC_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,63}$")


def _validate_session_id(v: str) -> str:
    if not 1 <= len(v) <= 128:
        raise ValueError("session_id must be 1-128 characters")
    if not _SESSION_ID_RE.match(v):
        raise ValueError("session_id must contain only alphanumeric, hyphen, or underscore characters")
    return v


SessionId = Annotated[str, AfterValidator(_validate_session_id)]
PlayerStance = Literal["observing", "hiding", "negotiating", "fleeing", "fighting"]
InjuryState = Literal["healthy", "injured", "critical"]


class ActiveTacticState(BaseModel):
    """One active tactical modifier with a bounded lifetime in turns."""

    name: str = Field(..., min_length=1, max_length=64)
    ttl: int = Field(default=1, ge=1, le=5)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        cleaned = str(value or "").strip().lower()
        if not _TACTIC_NAME_RE.match(cleaned):
            raise ValueError("tactic name must start with a letter and use letters, digits, underscore, dot, or hyphen")
        return cleaned


class StructuredCharacterState(BaseModel):
    """Canonical character-state fields enforced by the authoritative reducer."""

    stance: PlayerStance = "observing"
    focus: str = Field(default="", max_length=160)
    tactics: List[ActiveTacticState] = Field(default_factory=list)
    injury_state: InjuryState = "healthy"

    @field_validator("focus")
    @classmethod
    def _normalize_focus(cls, value: Any) -> str:
        return str(value or "").strip()[:160]

    @field_validator("tactics", mode="before")
    @classmethod
    def _normalize_tactics(cls, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            items = value
        else:
            items = [value]

        out: List[Any] = []
        seen: set[str] = set()
        for raw in items[:5]:
            if isinstance(raw, ActiveTacticState):
                tactic = raw
            elif isinstance(raw, dict):
                tactic = ActiveTacticState.model_validate(raw)
            else:
                tactic = ActiveTacticState(name=str(raw), ttl=1)
            if tactic.name in seen:
                continue
            seen.add(tactic.name)
            out.append(tactic)
        return out


class SessionBootstrapRequest(BaseModel):
    """Request model for onboarding-driven world bootstrap."""

    session_id: SessionId
    actor_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="Durable federation-scoped actor identity for resident or player sessions.",
    )
    world_theme: str = Field(default="", max_length=2000)
    player_role: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=10000)
    key_elements: List[str] = Field(default_factory=list)
    tone: str = Field(default="", max_length=500)
    bootstrap_source: str = Field(default="onboarding", min_length=1, max_length=40)
    world_id: Optional[SessionId] = Field(
        default=None,
        description="Join an existing shared world and share its event log.",
    )
    entry_location: Optional[str] = Field(
        default=None,
        max_length=80,
        description="Starting location for this session.",
    )


class WorldSeedRequest(BaseModel):
    """Request model for seeding a new world (admin operation, no character attached)."""

    world_theme: str = Field(..., min_length=1, max_length=2000)
    player_role: str = Field(default="inhabitant", min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=10000)
    key_elements: List[str] = Field(default_factory=list)
    tone: str = Field(default="grounded, observational", min_length=1, max_length=500)
    seed_from_city_pack: bool = Field(
        default=True,
        description=("When true, seed the world graph from the city pack (city_id). " "This deterministic geography path is the default for shard bring-up."),
    )
    enrich_city_pack: bool = Field(
        default=False,
        description=("When seed_from_city_pack=True, enrich city-pack nodes with LLM-written " "descriptions. Disabled by default so seed uses the pack's existing " "vibe/description fields."),
    )
    city_id: str = Field(
        default="san_francisco",
        description="City pack to use when seed_from_city_pack=True.",
    )
    world_id: Optional[str] = Field(
        default=None,
        description="If supplied, add this city pack to an existing world rather than creating a new one.",
    )


class WorldSeedResponse(BaseModel):
    """Response model for world seed endpoint."""

    success: bool = True
    world_id: str
    seeded_at: str
    message: str
    nodes_seeded: int = 0
    city_pack_used: Optional[str] = None


class SessionBootstrapResponse(BaseModel):
    """Response model for session bootstrap endpoint."""

    success: bool = True
    message: str
    session_id: SessionId
    vars: Dict[str, Any] = Field(default_factory=dict)
    theme: str
    player_role: str
    bootstrap_state: str = "completed"
    bootstrap_diagnostics: Optional[Dict[str, Any]] = None


class WorldFactItem(BaseModel):
    """Single world-fact assertion from structured LLM output."""

    subject: str = Field(..., min_length=1, max_length=200)
    subject_type: str = Field(default="entity", max_length=50)
    predicate: str = Field(..., min_length=1, max_length=200)
    value: Any
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    location: Optional[str] = Field(default=None, max_length=200)
    summary: Optional[str] = Field(default=None, max_length=500)


class WorldFactPayload(BaseModel):
    """Top-level envelope for structured world-fact extraction output."""

    facts: List[WorldFactItem] = Field(default_factory=list, max_length=50)
    parser_mode: str = Field(default="structured", max_length=50)


class WorldEventOut(BaseModel):
    """Response model for a single world event."""

    id: int
    session_id: Optional[str] = None
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


class PrefetchTriggerRequest(BaseModel):
    """Request model for scheduling one session frontier prefetch."""

    session_id: SessionId


class PrefetchTriggerResponse(BaseModel):
    """Response model for prefetch scheduling endpoint."""

    triggered: bool


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
