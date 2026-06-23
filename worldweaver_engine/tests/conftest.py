"""Shared test fixtures for all WorldWeaver tests.

Provides database isolation per test function and a pre-configured
FastAPI TestClient so individual test files need zero setup boilerplate.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Ensure the module-level DB engine points at a fresh temp file so the app
# lifespan (which seeds via background thread) never touches a stale schema.
# This must happen before any src.database import.
# ---------------------------------------------------------------------------
_tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_file.close()
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ["WW_DB_PATH"] = _tmp_file.name
os.environ["WW_ENABLE_CONSTELLATION"] = "0"
os.environ["WW_ENABLE_JIT_BEAT_GENERATION"] = "0"
# config.py disables .env loading under pytest, but its guard checks PYTEST_VERSION,
# which pytest < 8.1 does not set (and PYTEST_CURRENT_TEST is unset at import/collection
# time). Set it here, before any src import, so the suite runs against documented config
# defaults instead of a developer's local (gitignored) .env.
os.environ.setdefault("PYTEST_VERSION", pytest.__version__)

# Synthetic, era-agnostic resident roster. The DM/agent-validity paths resolve residents
# from WW_AGENT_RESIDENTS_DIR (real residents live per-shard under <shard>/residents/).
# Tests must not depend on a real shard roster or on the long-gone loops-era residents, so
# point the suite at a throwaway dir holding a couple of clearly-synthetic residents.
_residents_dir = tempfile.mkdtemp(suffix="-ww-test-residents")
for _resident in ("test_resident", "test_resident_two"):
    os.makedirs(os.path.join(_residents_dir, _resident, "identity"), exist_ok=True)
os.environ["WW_AGENT_RESIDENTS_DIR"] = _residents_dir
# Pin the demo-key window far into the future so the suite is wall-clock-independent.
# Action/turn tests exercise gameplay, not demo expiry; without this they 402 once the
# real demo date passes. Tests that DO exercise the expired path monkeypatch
# settings.demo_key_expires_at to a past date locally, so this default is harmless to them.
os.environ["WW_DEMO_KEY_EXPIRES_AT"] = "2099-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """Yield an isolated in-memory SQLAlchemy Session.

    Every test gets its own in-memory database so there is zero
    cross-contamination.  Global caches are cleared before and after
    each test.  The session is rolled back and closed automatically.
    """
    from src.database import Base
    from src.api.game import _state_managers
    from src.services.session_service import _session_locks
    from src.services.prefetch_service import clear_prefetch_cache

    _state_managers.clear()
    _session_locks.clear()
    clear_prefetch_cache()

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.rollback()
    session.close()
    engine.dispose()
    _state_managers.clear()
    _session_locks.clear()
    clear_prefetch_cache()


@pytest.fixture()
def seeded_db(db_session):
    """A db_session pre-populated with seed storylets."""
    from src.services.seed_data import seed_legacy_storylets_if_empty_sync

    seed_legacy_storylets_if_empty_sync(db_session)
    db_session.commit()
    return db_session


# ---------------------------------------------------------------------------
# FastAPI TestClient fixtures
# ---------------------------------------------------------------------------


def _make_client(db):
    """Build a TestClient whose get_db dependency returns *db*."""
    from src.database import get_db, create_tables
    from src.api.game import _state_managers
    from src.services.session_service import _session_locks
    from main import app

    # Ensure the module-level file DB has up-to-date schema so the
    # lifespan seed (which runs against the file DB) doesn't crash.
    create_tables()

    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    _state_managers.clear()
    _session_locks.clear()
    return app, _state_managers


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient backed by the isolated db_session."""
    from fastapi.testclient import TestClient

    app, sm = _make_client(db_session)
    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc
    sm.clear()
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_client(seeded_db):
    """FastAPI TestClient backed by a seeded in-memory database."""
    from fastapi.testclient import TestClient

    app, sm = _make_client(seeded_db)
    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc
    sm.clear()
    app.dependency_overrides.clear()
