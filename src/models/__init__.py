"""Database models."""

from datetime import datetime
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


class Storylet(Base):
    """Model for interactive fiction storylets."""

    __tablename__ = "storylets"

    id = Column(Integer, primary_key=True)
    # Title should be unique to prevent accidental duplicate storylets
    title = Column(String(200), nullable=False, unique=True)
    text_template = Column(Text, nullable=False)
    requires = Column(JSON, default=dict)
    choices = Column(JSON, default=list)
    weight = Column(Float, default=1.0)
    position = Column(JSON, default=lambda: {"x": 0, "y": 0})  # Position for spatial navigation
    embedding = Column(JSON, nullable=True)  # Vector embedding for semantic selection
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SessionVars(Base):
    """Model for storing session variables."""

    __tablename__ = "session_vars"

    session_id = Column(String(64), primary_key=True)
    vars = Column(JSON, default=dict)
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
    __table_args__ = (
        UniqueConstraint("node_type", "normalized_name", name="uq_world_nodes_type_name"),
    )

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


class WorldProjection(Base):
    """Current world-state projection derived from world events."""

    __tablename__ = "world_projection"
    __table_args__ = (
        UniqueConstraint("path", name="uq_world_projection_path"),
    )

    id = Column(Integer, primary_key=True)
    path = Column(String(255), nullable=False)
    value = Column(JSON, nullable=True)
    is_deleted = Column(Boolean, default=False)
    confidence = Column(Float, default=1.0)
    source_event_id = Column(Integer, ForeignKey("world_events.id"), nullable=True)
    metadata_json = Column(JSON, default=dict)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
