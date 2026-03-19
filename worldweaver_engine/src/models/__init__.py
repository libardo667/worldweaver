"""Database models."""

import uuid as _uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from ..database import Base


@dataclass
class NarrativeBeat:
    """Temporary thematic lens that warps semantic storylet selection."""

    name: str
    intensity: float = 0.35
    turns_remaining: int = 3
    decay: float = 0.65
    vector: Optional[list[float]] = None
    source: str = "system"

    def is_active(self) -> bool:
        """True when the beat can still influence selection."""
        return self.turns_remaining > 0 and self.intensity > 0.0

    def consume_turn(self) -> None:
        """Advance one turn and decay intensity."""
        self.turns_remaining = max(0, int(self.turns_remaining) - 1)
        self.intensity = max(0.0, float(self.intensity) * max(0.0, float(self.decay)))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize beat for session persistence."""
        return {
            "name": self.name,
            "intensity": float(self.intensity),
            "turns_remaining": int(self.turns_remaining),
            "decay": float(self.decay),
            "vector": list(self.vector) if self.vector else None,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "NarrativeBeat":
        """Create beat from persisted payload."""
        return cls(
            name=str(payload.get("name", "ThematicResonance")),
            intensity=float(payload.get("intensity", 0.35)),
            turns_remaining=max(0, int(payload.get("turns_remaining", 3))),
            decay=float(payload.get("decay", 0.65)),
            vector=payload.get("vector"),
            source=str(payload.get("source", "system")),
        )


class Player(Base):
    """Registered player account."""

    __tablename__ = "players"

    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    actor_id = Column(String(36), unique=True, nullable=True, index=True)
    email = Column(String(254), unique=True, nullable=False, index=True)
    username = Column(String(40), unique=True, nullable=False, index=True)
    display_name = Column(String(120), nullable=False)
    password_hash = Column(String(128), nullable=False)
    api_key_enc = Column(Text, nullable=True)
    pass_type = Column(String(20), nullable=False, default="visitor_7day")
    pass_expires_at = Column(DateTime, nullable=True)   # null = permanent citizen
    terms_accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Storylet(Base):
    """Model for interactive fiction storylets."""

    __tablename__ = "storylets"

    id = Column(Integer, primary_key=True)
    # Title should be unique to prevent accidental duplicate storylets
    title = Column(String(200), nullable=False, unique=True)
    text_template = Column(Text, nullable=False)
    requires = Column(JSON, default=dict)
    choices = Column(JSON, default=list)
    effects = Column(JSON, default=list)
    weight = Column(Float, default=1.0)
    position = Column(JSON, default=lambda: {"x": 0, "y": 0})  # Position for spatial navigation
    embedding = Column(JSON, nullable=True)  # Vector embedding for semantic selection
    source = Column(String(50), nullable=False, default="authored")
    seed_event_ids = Column(JSON, default=list)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SessionVars(Base):
    """Model for storing session variables."""

    __tablename__ = "session_vars"

    session_id = Column(String(64), primary_key=True)
    vars = Column(JSON, default=dict)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    player_id = Column(String(36), ForeignKey("players.id"), nullable=True)
    actor_id = Column(String(36), nullable=True, index=True)


class ResidentIdentityGrowth(Base):
    """Actor-scoped mutable identity growth and note evidence."""

    __tablename__ = "resident_identity_growth"

    actor_id = Column(String(36), primary_key=True)
    growth_text = Column(Text, nullable=False, default="")
    growth_metadata = Column(JSON, default=dict)
    note_records = Column(JSON, default=list)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WorldEvent(Base):
    """Persistent record of world-changing events."""

    __tablename__ = "world_events"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), nullable=True)
    storylet_id = Column(Integer, nullable=True)
    event_type = Column(String(50), nullable=False)
    summary = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)
    world_state_delta = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())


class WorldNode(Base):
    """Typed graph node representing a world concept/entity/location."""

    __tablename__ = "world_nodes"
    __table_args__ = (UniqueConstraint("node_type", "normalized_name", name="uq_world_nodes_type_name"),)

    id = Column(Integer, primary_key=True)
    node_type = Column(String(50), nullable=False, default="concept")
    name = Column(String(200), nullable=False)
    normalized_name = Column(String(200), nullable=False)
    embedding = Column(JSON, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WorldEdge(Base):
    """Typed relationship between two world nodes."""

    __tablename__ = "world_edges"
    __table_args__ = (
        UniqueConstraint(
            "source_node_id",
            "target_node_id",
            "edge_type",
            name="uq_world_edges_source_target_type",
        ),
    )

    id = Column(Integer, primary_key=True)
    source_node_id = Column(Integer, ForeignKey("world_nodes.id"), nullable=False)
    target_node_id = Column(Integer, ForeignKey("world_nodes.id"), nullable=False)
    edge_type = Column(String(80), nullable=False)
    weight = Column(Float, default=1.0)
    confidence = Column(Float, default=0.75)
    source_event_id = Column(Integer, ForeignKey("world_events.id"), nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WorldFact(Base):
    """Persistent assertion extracted from world events."""

    __tablename__ = "world_facts"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), nullable=True)
    subject_node_id = Column(Integer, ForeignKey("world_nodes.id"), nullable=False)
    location_node_id = Column(Integer, ForeignKey("world_nodes.id"), nullable=True)
    predicate = Column(String(120), nullable=False)
    value = Column(JSON, nullable=False, default=dict)
    confidence = Column(Float, default=0.75)
    is_active = Column(Boolean, default=True)
    valid_from = Column(DateTime, server_default=func.now())
    valid_to = Column(DateTime, nullable=True)
    source_event_id = Column(Integer, ForeignKey("world_events.id"), nullable=True)
    summary = Column(Text, nullable=False, default="")
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LocationChat(Base):
    """Lightweight co-located chat message — not narrated, not a world event."""

    __tablename__ = "location_chat"

    id = Column(Integer, primary_key=True, autoincrement=True)
    location = Column(String(200), nullable=False, index=True)
    session_id = Column(String(64), nullable=False)
    display_name = Column(String(200), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)


class DoulaPoll(Base):
    """Doula classification poll — tracks agent votes on ambiguous candidate names.

    Created when the doula finds a candidate it can't classify with confidence.
    Agents cast votes via the API (AGENT or STATIC). When the poll expires or
    all votes are in, the doula resolves it and either spawns an agent or
    injects a place node.
    """

    __tablename__ = "doula_polls"

    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    candidate_name = Column(String(200), nullable=False, index=True)
    context_json = Column(JSON, default=list)        # list[str] — narrative evidence
    entry_location = Column(String(200), nullable=True)
    entity_class = Column(String(50), nullable=False)  # "novel" | "player_shadow"
    weight = Column(Float, default=0.0)
    expires_at = Column(DateTime, nullable=False)
    voters_json = Column(JSON, default=list)          # list[str] — session_id strings
    votes_json = Column(JSON, default=dict)           # {voter_session_id → "AGENT"|"STATIC"}
    resolved_at = Column(DateTime, nullable=True)
    outcome = Column(String(20), nullable=True)       # "agent" | "static" | None
    created_at = Column(DateTime, server_default=func.now())


class DirectMessage(Base):
    """Private async message between a player and an agent (or agent→agent)."""

    __tablename__ = "direct_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_name = Column(String(60), nullable=False)
    from_session_id = Column(String(64), nullable=True, index=True)  # reply routing
    to_name = Column(String(64), nullable=False, index=True)          # agent slug or player session_id
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime, server_default=func.now(), index=True)
    read_at = Column(DateTime, nullable=True)                         # NULL = unread


class FederationShard(Base):
    """Registered shard in the federation network."""

    __tablename__ = "federation_shards"

    shard_id = Column(String(80), primary_key=True)
    shard_url = Column(String(255), nullable=False)
    shard_type = Column(String(20), nullable=False, default="city")  # city|world|neighborhood
    city_id = Column(String(80), nullable=True)
    last_pulse_ts = Column(DateTime, nullable=True)
    last_pulse_seq = Column(Integer, nullable=True, default=0)
    registered_at = Column(DateTime, server_default=func.now())


class FederationActor(Base):
    """Canonical federation-wide identity for humans and agents."""

    __tablename__ = "federation_actors"

    actor_id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    actor_type = Column(String(20), nullable=False, default="human")  # human|agent|player_shadow
    display_name = Column(String(120), nullable=False)
    handle = Column(String(80), nullable=True, unique=True, index=True)
    home_shard = Column(String(80), nullable=False)
    current_shard = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    origin = Column(String(20), nullable=False, default="migrated")
    source_actor_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class FederationActorAuth(Base):
    """Canonical human auth record stored at the federation root."""

    __tablename__ = "federation_actor_auth"

    actor_id = Column(String(36), primary_key=True)
    email = Column(String(254), unique=True, nullable=False, index=True)
    username = Column(String(40), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    pass_type = Column(String(20), nullable=False, default="visitor_7day")
    pass_expires_at = Column(DateTime, nullable=True)
    terms_accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class FederationActorSecret(Base):
    """Encrypted actor-linked secrets such as BYOK credentials."""

    __tablename__ = "federation_actor_secrets"

    actor_id = Column(String(36), primary_key=True)
    llm_api_key_enc = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    rotated_at = Column(DateTime, nullable=True)


class FederationResident(Base):
    """Cross-shard resident record maintained by ww_world/."""

    __tablename__ = "federation_residents"

    resident_id = Column(String(36), primary_key=True)   # UUID — durable identity
    name = Column(String(120), nullable=False, index=True)
    home_shard = Column(String(80), nullable=False)
    current_shard = Column(String(80), nullable=False)
    last_location = Column(String(200), nullable=True)
    last_act_ts = Column(DateTime, nullable=True)
    resident_type = Column(String(20), nullable=False, default="agent")  # agent|player
    status = Column(String(20), nullable=False, default="active")
    # status: active | dormant | traveling | missing | retired
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class FederationTraveler(Base):
    """Log of cross-shard travel events."""

    __tablename__ = "federation_travelers"

    id = Column(Integer, primary_key=True)
    resident_id = Column(String(36), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    from_shard = Column(String(80), nullable=False)
    to_shard = Column(String(80), nullable=False)
    departed_ts = Column(DateTime, nullable=True)
    arrived_ts = Column(DateTime, nullable=True)


class FederationMessage(Base):
    """Durable cross-shard DM mailbox maintained by ww_world/."""

    __tablename__ = "federation_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_resident_id = Column(String(36), nullable=False)
    from_shard = Column(String(80), nullable=False)
    to_resident_id = Column(String(36), nullable=False, index=True)
    to_shard = Column(String(80), nullable=False, index=True)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime, server_default=func.now())
    delivered_at = Column(DateTime, nullable=True)


class WorldProjection(Base):
    """Current world-state projection derived from world events."""

    __tablename__ = "world_projection"
    __table_args__ = (UniqueConstraint("path", name="uq_world_projection_path"),)

    id = Column(Integer, primary_key=True)
    path = Column(String(255), nullable=False)
    value = Column(JSON, nullable=True)
    is_deleted = Column(Boolean, default=False)
    confidence = Column(Float, default=1.0)
    source_event_id = Column(Integer, ForeignKey("world_events.id"), nullable=True)
    metadata_json = Column(JSON, default=dict)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
