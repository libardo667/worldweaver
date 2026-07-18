# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Database models."""

import uuid as _uuid
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from ..database import Base


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
    pass_type = Column(String(20), nullable=False, default="citizen")
    pass_expires_at = Column(DateTime, nullable=True)
    terms_accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


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
    growth_proposals = Column(JSON, default=list)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WorldEvent(Base):
    """Persistent record of world-changing events."""

    __tablename__ = "world_events"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), nullable=True)
    event_type = Column(String(50), nullable=False)
    summary = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)
    world_state_delta = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())


class DurableObject(Base):
    """Canonical shard-local object with exactly one current attachment."""

    __tablename__ = "durable_objects"
    __table_args__ = (
        CheckConstraint(
            "(custodian_actor_id IS NOT NULL AND location IS NULL) OR " "(custodian_actor_id IS NULL AND location IS NOT NULL)",
            name="ck_durable_objects_one_attachment",
        ),
        Index("ix_durable_objects_custodian_status", "custodian_actor_id", "status"),
        Index("ix_durable_objects_location_status", "location", "status"),
        Index("ix_durable_objects_placed_by_status", "placed_by_actor_id", "status"),
    )

    object_id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False, default="")
    object_kind = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    custodian_actor_id = Column(String(36), nullable=True)
    location = Column(String(200), nullable=True)
    # Ordinary placement keeps a reclaim claim for the actor who put the object
    # down. A null claim means a different bounded attachment (for example a stoop)
    # owns the take rules.
    placed_by_actor_id = Column(String(36), nullable=True)
    origin_shard_id = Column(String(80), nullable=False)
    created_by_actor_id = Column(String(36), nullable=False)
    provenance_kind = Column(String(40), nullable=False)
    provenance_ref = Column(String(120), nullable=True)
    provenance_event_id = Column(Integer, ForeignKey("world_events.id", ondelete="RESTRICT"), nullable=True, index=True)
    properties_json = Column(JSON, nullable=False, default=dict)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ConsequenceReceipt(Base):
    """Append-only evidence for one accepted durable-object command."""

    __tablename__ = "consequence_receipts"
    __table_args__ = (
        UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_consequence_receipts_actor_idempotency",
        ),
        Index("ix_consequence_receipts_object_created", "object_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(String(36), nullable=False, unique=True, default=lambda: str(_uuid.uuid4()))
    actor_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    operation = Column(String(50), nullable=False)
    object_id = Column(String(36), ForeignKey("durable_objects.object_id", ondelete="RESTRICT"), nullable=False)
    world_event_id = Column(Integer, ForeignKey("world_events.id", ondelete="RESTRICT"), nullable=False, unique=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class ObjectExchange(Base):
    """One exact two-party object swap proposed by the current holder."""

    __tablename__ = "object_exchanges"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'completed', 'declined', 'cancelled')",
            name="ck_object_exchanges_known_status",
        ),
        CheckConstraint(
            "proposer_actor_id <> recipient_actor_id",
            name="ck_object_exchanges_distinct_actors",
        ),
        CheckConstraint(
            "offered_object_id <> requested_object_id",
            name="ck_object_exchanges_distinct_objects",
        ),
        Index("ix_object_exchanges_proposer_status", "proposer_actor_id", "status"),
        Index("ix_object_exchanges_recipient_status", "recipient_actor_id", "status"),
    )

    exchange_id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    proposer_actor_id = Column(String(36), nullable=False)
    recipient_actor_id = Column(String(36), nullable=False)
    offered_object_id = Column(
        String(36),
        ForeignKey("durable_objects.object_id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_object_id = Column(
        String(36),
        ForeignKey("durable_objects.object_id", ondelete="RESTRICT"),
        nullable=False,
    )
    offered_object_revision = Column(Integer, nullable=False)
    requested_object_revision = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="open")
    offered_at_location = Column(String(200), nullable=False)
    completed_at_location = Column(String(200), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime, nullable=True)


class ExchangeReceipt(Base):
    """Append-only public evidence for an exchange command."""

    __tablename__ = "exchange_receipts"
    __table_args__ = (
        UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_exchange_receipts_actor_idempotency",
        ),
        Index("ix_exchange_receipts_exchange_created", "exchange_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(String(36), nullable=False, unique=True, default=lambda: str(_uuid.uuid4()))
    actor_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    operation = Column(String(50), nullable=False)
    exchange_id = Column(
        String(36),
        ForeignKey("object_exchanges.exchange_id", ondelete="RESTRICT"),
        nullable=False,
    )
    world_event_id = Column(
        Integer,
        ForeignKey("world_events.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    payload_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class WorldStoop(Base):
    """A bounded, node-owned object exchange point at one exact place."""

    __tablename__ = "world_stoops"
    __table_args__ = (
        CheckConstraint("capacity > 0 AND capacity <= 50", name="ck_world_stoops_bounded_capacity"),
        Index("ix_world_stoops_location", "location"),
    )

    stoop_id = Column(String(80), primary_key=True)
    title = Column(String(120), nullable=False)
    prompt = Column(String(500), nullable=False, default="")
    location = Column(String(200), nullable=False)
    capacity = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class StoopObjectEntry(Base):
    """Current/history projection for one durable object deliberately left on a stoop."""

    __tablename__ = "stoop_object_entries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'taken', 'withdrawn')",
            name="ck_stoop_object_entries_known_status",
        ),
        Index("ix_stoop_object_entries_stoop_status", "stoop_id", "status"),
        Index("ix_stoop_object_entries_object_status", "object_id", "status"),
    )

    entry_id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    stoop_id = Column(
        String(80),
        ForeignKey("world_stoops.stoop_id", ondelete="RESTRICT"),
        nullable=False,
    )
    object_id = Column(
        String(36),
        ForeignKey("durable_objects.object_id", ondelete="RESTRICT"),
        nullable=False,
    )
    left_by_actor_id = Column(String(36), nullable=False)
    taken_by_actor_id = Column(String(36), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    object_revision_at_leave = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime, nullable=True)


class StoopReceipt(Base):
    """Append-only public evidence for a single-instance stoop command."""

    __tablename__ = "stoop_receipts"
    __table_args__ = (
        UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_stoop_receipts_actor_idempotency",
        ),
        Index("ix_stoop_receipts_entry_created", "entry_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(String(36), nullable=False, unique=True, default=lambda: str(_uuid.uuid4()))
    actor_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    operation = Column(String(50), nullable=False)
    entry_id = Column(
        String(36),
        ForeignKey("stoop_object_entries.entry_id", ondelete="RESTRICT"),
        nullable=False,
    )
    world_event_id = Column(
        Integer,
        ForeignKey("world_events.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    payload_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class MaterialPool(Base):
    """One replenishing, non-essential material source at an exact place."""

    __tablename__ = "material_pools"
    __table_args__ = (
        UniqueConstraint(
            "ruleset_id",
            "ruleset_version",
            "material_id",
            "location",
            name="uq_material_pools_ruleset_material_location",
        ),
        CheckConstraint("capacity_units > 0", name="ck_material_pools_positive_capacity"),
        CheckConstraint("available_units >= 0 AND available_units <= capacity_units", name="ck_material_pools_bounded_available"),
        CheckConstraint("replenish_units > 0 AND replenish_every_seconds > 0", name="ck_material_pools_positive_replenishment"),
        Index("ix_material_pools_ruleset_location", "ruleset_id", "ruleset_version", "location"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ruleset_id = Column(String(80), nullable=False)
    ruleset_version = Column(String(40), nullable=False)
    material_id = Column(String(80), nullable=False)
    title = Column(String(120), nullable=False)
    location = Column(String(200), nullable=False)
    capacity_units = Column(Integer, nullable=False)
    starting_units = Column(Integer, nullable=False)
    available_units = Column(Integer, nullable=False)
    replenish_units = Column(Integer, nullable=False)
    replenish_every_seconds = Column(Integer, nullable=False)
    last_replenished_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SpaceAccessPolicy(Base):
    """Current entry rule for one exact place on an opted-in game shard."""

    __tablename__ = "space_access_policies"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('public', 'requestable', 'private', 'closed')",
            name="ck_space_access_policies_known_mode",
        ),
    )

    location = Column(String(200), primary_key=True)
    mode = Column(String(20), nullable=False, default="public")
    controller_actor_id = Column(String(36), nullable=False, index=True)
    note = Column(String(500), nullable=False, default="")
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SpaceAccessGrant(Base):
    """Current actor-scoped admission to one controlled place."""

    __tablename__ = "space_access_grants"
    __table_args__ = (
        UniqueConstraint("location", "actor_id", name="uq_space_access_grants_location_actor"),
        Index("ix_space_access_grants_actor_active", "actor_id", "active"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    location = Column(
        String(200),
        ForeignKey("space_access_policies.location", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_id = Column(String(36), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    granted_by_actor_id = Column(String(36), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SpaceAccessRequest(Base):
    """One elective request to enter a requestable place."""

    __tablename__ = "space_access_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'admitted', 'denied', 'withdrawn')",
            name="ck_space_access_requests_known_status",
        ),
        Index("ix_space_access_requests_location_status", "location", "status"),
    )

    request_id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    location = Column(
        String(200),
        ForeignKey("space_access_policies.location", ondelete="RESTRICT"),
        nullable=False,
    )
    requester_actor_id = Column(String(36), nullable=False, index=True)
    requester_session_id = Column(String(64), nullable=False)
    note = Column(String(500), nullable=False, default="")
    status = Column(String(20), nullable=False, default="pending")
    resolved_by_actor_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime, nullable=True)


class SpaceAccessReceipt(Base):
    """Append-only evidence for a successful access command."""

    __tablename__ = "space_access_receipts"
    __table_args__ = (
        UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_space_access_receipts_actor_idempotency",
        ),
        Index("ix_space_access_receipts_location_created", "location", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(String(36), nullable=False, unique=True, default=lambda: str(_uuid.uuid4()))
    actor_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    operation = Column(String(50), nullable=False)
    location = Column(String(200), nullable=False)
    world_event_id = Column(
        Integer,
        ForeignKey("world_events.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    payload_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


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


class WorldTrace(Base):
    """A local, expiring physical mark left in the shared world.

    Traces are deliberately not chat and not generic world events. They stay
    attached to one location, retain their author, and disappear from perception
    after ``expires_at`` without deleting their historical row.
    """

    __tablename__ = "world_traces"
    __table_args__ = (Index("ix_world_traces_location_expires_at", "location", "expires_at"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    author_name = Column(String(200), nullable=False)
    location = Column(String(200), nullable=False, index=True)
    target = Column(String(200), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


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
    context_json = Column(JSON, default=list)  # list[str] — narrative evidence
    entry_location = Column(String(200), nullable=True)
    entity_class = Column(String(50), nullable=False)  # "novel" | "player_shadow"
    weight = Column(Float, default=0.0)
    expires_at = Column(DateTime, nullable=False)
    voters_json = Column(JSON, default=list)  # list[str] — session_id strings
    votes_json = Column(JSON, default=dict)  # {voter_session_id → "AGENT"|"STATIC"}
    resolved_at = Column(DateTime, nullable=True)
    outcome = Column(String(20), nullable=True)  # "agent" | "static" | None
    created_at = Column(DateTime, server_default=func.now())


class DirectMessage(Base):
    """Private async message between a player and an agent (or agent→agent)."""

    __tablename__ = "direct_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_name = Column(String(60), nullable=False)
    from_session_id = Column(String(64), nullable=True, index=True)  # reply routing
    to_name = Column(String(64), nullable=False, index=True)  # agent slug or player session_id
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime, server_default=func.now(), index=True)
    read_at = Column(DateTime, nullable=True)  # NULL = unread


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
    """Federation coordination projection for a durable actor identity."""

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
    password_reset_token_hash = Column(String(128), nullable=True)
    password_reset_expires_at = Column(DateTime, nullable=True)
    password_reset_requested_at = Column(DateTime, nullable=True)
    pass_type = Column(String(20), nullable=False, default="citizen")
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
    """Cross-shard resident presence projection maintained by ww_world/."""

    __tablename__ = "federation_residents"

    resident_id = Column(String(36), primary_key=True)  # UUID — durable identity
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
    """Federation-coordinated lifecycle for one actor crossing between nodes."""

    __tablename__ = "federation_travelers"

    id = Column(Integer, primary_key=True)
    travel_id = Column(String(64), nullable=False, unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    resident_id = Column(String(36), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    from_shard = Column(String(80), nullable=False)
    to_shard = Column(String(80), nullable=False)
    actor_type = Column(String(20), nullable=False, default="agent")
    status = Column(String(20), nullable=False, default="departing")
    departure_hub_id = Column(String(80), nullable=True)
    departure_hub = Column(String(200), nullable=True)
    arrival_hub_id = Column(String(80), nullable=True)
    arrival_hub = Column(String(200), nullable=True)
    reason = Column(String(255), nullable=True)
    requested_ts = Column(DateTime, server_default=func.now(), nullable=False)
    departed_ts = Column(DateTime, nullable=True)
    arrived_ts = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ShardTravelHandoff(Base):
    """A node-local recovery record while it performs its side of a trip."""

    __tablename__ = "shard_travel_handoffs"

    travel_id = Column(String(64), primary_key=True)
    actor_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(128), nullable=True)
    owner_player_id = Column(String(36), nullable=True)
    role = Column(String(20), nullable=False)
    source_shard = Column(String(80), nullable=False)
    destination_shard = Column(String(80), nullable=False)
    destination_url = Column(String(255), nullable=True)
    route_id = Column(String(80), nullable=True)
    departure_hub_id = Column(String(80), nullable=True)
    departure_hub = Column(String(200), nullable=True)
    arrival_hub_id = Column(String(80), nullable=True)
    arrival_hub = Column(String(200), nullable=True)
    status = Column(String(40), nullable=False, default="prepared")
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


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
