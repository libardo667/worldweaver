"""Tests for database environment variable logic.

These tests verify that the module-level variable selection in
src/database.py works correctly under different environment configurations.

Because we need to re-import src.database to test module-level behavior,
we save and restore sys.modules to avoid poisoning subsequent tests.
"""

import os
import sys
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _preserve_database_module():
    """Save and restore all src.database* entries in sys.modules."""
    saved = {k: v for k, v in sys.modules.items() if "src.database" in k}
    yield
    # Remove any reimported versions
    for k in list(sys.modules):
        if "src.database" in k:
            del sys.modules[k]
    # Restore originals
    sys.modules.update(saved)


def _reimport_database():
    """Force re-import of src.database to pick up new env vars."""
    mods = [m for m in sys.modules if "src.database" in m]
    for m in mods:
        del sys.modules[m]
    from src.database import database_url, db_file, engine, engine_kwargs

    return database_url, db_file, engine, engine_kwargs


class TestDatabaseEnvironmentLogic:

    @patch.dict(os.environ, {"WW_DB_PATH": "custom_database.db"}, clear=False)
    def test_custom_db_path_environment_variable(self):
        database_url, db_file, engine, _ = _reimport_database()
        assert db_file == "custom_database.db"
        assert database_url == "sqlite:///custom_database.db"
        assert "custom_database.db" in str(engine.url)

    @patch.dict(os.environ, {"WW_DB_PATH": "/absolute/path/to/database.db"}, clear=False)
    def test_absolute_db_path_environment_variable(self):
        _, db_file, engine, _ = _reimport_database()
        assert db_file == "/absolute/path/to/database.db"
        assert str(engine.url) == "sqlite:////absolute/path/to/database.db"

    @patch.dict(
        os.environ,
        {
            "WW_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/worldweaver",
            "WW_DB_PATH": "ignored.db",
        },
        clear=False,
    )
    def test_database_url_takes_precedence_over_db_path(self):
        database_url, db_file, engine, engine_kwargs = _reimport_database()
        assert db_file is None
        assert database_url == "postgresql+psycopg://postgres:postgres@localhost:5432/worldweaver"
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.url.host == "localhost"
        assert engine.url.database == "worldweaver"
        assert engine_kwargs["pool_size"] == 12

    @patch.dict(
        os.environ,
        {
            "WW_DB_HOST": "db",
            "WW_DB_PORT": "5432",
            "WW_DB_NAME": "worldweaver_sfo",
            "WW_DB_USER": "postgres",
            "WW_DB_PASSWORD": "postgres",
        },
        clear=False,
    )
    def test_component_db_settings_build_postgres_url(self):
        database_url, db_file, engine, engine_kwargs = _reimport_database()
        assert db_file is None
        assert database_url == "postgresql+psycopg://postgres:postgres@db:5432/worldweaver_sfo"
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.url.host == "db"
        assert engine.url.database == "worldweaver_sfo"
        assert engine_kwargs["max_overflow"] == 24
        assert engine_kwargs["pool_pre_ping"] is True

    @patch.dict(
        os.environ,
        {
            "WW_DB_HOST": "db",
            "WW_DB_PORT": "5432",
            "WW_DB_NAME": "worldweaver_sfo",
            "WW_DB_USER": "postgres",
            "WW_DB_PASSWORD": "postgres",
            "WW_DB_POOL_SIZE": "20",
            "WW_DB_MAX_OVERFLOW": "40",
            "WW_DB_POOL_TIMEOUT": "45",
            "WW_DB_POOL_RECYCLE": "900",
            "WW_DB_POOL_PRE_PING": "false",
            "WW_DB_POOL_USE_LIFO": "false",
        },
        clear=False,
    )
    def test_postgres_pool_settings_are_env_driven(self):
        _, _, _, engine_kwargs = _reimport_database()
        assert engine_kwargs["pool_size"] == 20
        assert engine_kwargs["max_overflow"] == 40
        assert engine_kwargs["pool_timeout"] == 45
        assert engine_kwargs["pool_recycle"] == 900
        assert engine_kwargs["pool_pre_ping"] is False
        assert engine_kwargs["pool_use_lifo"] is False

    @patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "test_something"}, clear=False)
    def test_pytest_environment_uses_test_database(self):
        if "WW_DB_PATH" in os.environ:
            del os.environ["WW_DB_PATH"]
        if "WW_DATABASE_URL" in os.environ:
            del os.environ["WW_DATABASE_URL"]
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]
        _, db_file, _, _ = _reimport_database()
        assert db_file == "test_database.db"

    def test_database_engine_configuration(self):
        from src.database import engine

        assert str(engine.url).startswith("sqlite:///")

    def test_session_local_configuration(self):
        from src.database import SessionLocal

        sf = SessionLocal.session_factory
        assert sf.kw.get("autoflush") is False
        assert sf.kw.get("autocommit") is False

    def test_get_db_generator_function(self):
        from src.database import get_db
        from sqlalchemy.orm import Session

        gen = get_db()
        session = next(gen)
        assert isinstance(session, Session)
        gen.close()

    def test_multiple_environment_scenarios(self):
        scenarios = [
            ("custom.db", None, "custom.db"),
            (None, "test_file", "test_database.db"),
            ("/abs/db.sqlite", "test", "/abs/db.sqlite"),
        ]
        for dw_db_path, pytest_test, expected in scenarios:
            mods = [m for m in sys.modules if "src.database" in m]
            for m in mods:
                del sys.modules[m]
            env = {}
            if dw_db_path is not None:
                env["WW_DB_PATH"] = dw_db_path
            if pytest_test is not None:
                env["PYTEST_CURRENT_TEST"] = pytest_test
            with patch.dict(os.environ, env, clear=True):
                from src.database import db_file

                assert db_file == expected, f"Failed for WW_DB_PATH={dw_db_path}, PYTEST={pytest_test}"
