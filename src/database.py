"""Database configuration and setup.

Respects DW_DB_PATH (absolute or relative sqlite file path). During pytest runs,
defaults to test_database.db unless DW_DB_PATH is set.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import os

# Database Setup
db_file = os.environ.get("DW_DB_PATH")
if not db_file:
    # If running under pytest, prefer the test DB by default
    db_file = "test_database.db" if os.environ.get("PYTEST_CURRENT_TEST") else "worldweaver.db"

engine = create_engine(f"sqlite:///{db_file}", future=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
# Compatibility shim for tests expecting a scoped_session-like attribute.
if not hasattr(SessionLocal, "session_factory"):
    SessionLocal.session_factory = SessionLocal
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(engine)
