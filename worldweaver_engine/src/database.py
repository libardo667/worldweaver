"""Database configuration and setup.

Prefers WW_DATABASE_URL / DATABASE_URL when provided so non-SQLite backends
can be used directly. Otherwise falls back to WW_DB_PATH and the historical
local SQLite defaults.
"""

import os
from typing import Generator, Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker


def _normalize_database_url(url: str) -> str:
    """Normalize DB URLs onto the project's supported SQLAlchemy drivers."""
    normalized = str(url or "").strip()
    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+psycopg://", 1)
    return normalized


def _build_postgres_url_from_parts() -> Optional[str]:
    """Build a Postgres URL from discrete shard DB environment variables."""
    host = str(os.environ.get("WW_DB_HOST") or "").strip()
    name = str(os.environ.get("WW_DB_NAME") or "").strip()
    if not host or not name:
        return None

    user = str(os.environ.get("WW_DB_USER") or "postgres").strip() or "postgres"
    password = str(os.environ.get("WW_DB_PASSWORD") or "postgres")
    port = str(os.environ.get("WW_DB_PORT") or "5432").strip() or "5432"
    return (
        "postgresql+psycopg://"
        f"{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(name)}"
    )


def resolve_database_url() -> tuple[str, Optional[str]]:
    """Resolve the SQLAlchemy URL and legacy sqlite db file, if any."""
    explicit_url = (
        os.environ.get("WW_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    if explicit_url:
        return _normalize_database_url(explicit_url), None

    component_url = _build_postgres_url_from_parts()
    if component_url:
        return component_url, None

    db_file = os.environ.get("WW_DB_PATH")
    if not db_file:
        # If running under pytest, prefer the test DB by default.
        db_file = (
            "test_database.db"
            if os.environ.get("PYTEST_CURRENT_TEST")
            else "db/worldweaver.db"
        )
    return f"sqlite:///{db_file}", db_file


database_url, db_file = resolve_database_url()
is_sqlite = database_url.startswith("sqlite")

engine = create_engine(
    database_url,
    future=True,
    connect_args={"check_same_thread": False} if is_sqlite else {},
)


@event.listens_for(engine, "connect")
def _configure_sqlite_connection(dbapi_conn, connection_record):
    """Enable SQLite-specific pragmas for local dev concurrency."""
    if not is_sqlite:
        return
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA busy_timeout=30000")
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
