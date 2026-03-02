"""Database models."""

from datetime import datetime
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, func
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
