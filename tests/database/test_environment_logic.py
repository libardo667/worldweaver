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
    from src.database import db_file, engine

    return db_file, engine


class TestDatabaseEnvironmentLogic:

    @patch.dict(os.environ, {"DW_DB_PATH": "custom_database.db"}, clear=False)
    def test_custom_db_path_environment_variable(self):
        db_file, engine = _reimport_database()
        assert db_file == "custom_database.db"
        assert "custom_database.db" in str(engine.url)

    @patch.dict(os.environ, {"DW_DB_PATH": "/absolute/path/to/database.db"}, clear=False)
    def test_absolute_db_path_environment_variable(self):
        db_file, engine = _reimport_database()
        assert db_file == "/absolute/path/to/database.db"

    @patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "test_something"}, clear=False)
    def test_pytest_environment_uses_test_database(self):
        if "DW_DB_PATH" in os.environ:
            del os.environ["DW_DB_PATH"]
        db_file, _ = _reimport_database()
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
                env["DW_DB_PATH"] = dw_db_path
            if pytest_test is not None:
                env["PYTEST_CURRENT_TEST"] = pytest_test
            with patch.dict(os.environ, env, clear=True):
                from src.database import db_file

                assert db_file == expected, f"Failed for DW_DB_PATH={dw_db_path}, PYTEST={pytest_test}"
