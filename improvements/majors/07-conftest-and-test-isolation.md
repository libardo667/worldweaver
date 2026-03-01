# Add shared conftest.py and proper test database isolation

## Problem

There is no `conftest.py` anywhere in the test tree. Every test file that
needs a database or a `TestClient` must set up its own fixtures, leading to
duplicated boilerplate and inconsistent isolation. Some tests rely on the
implicit `PYTEST_CURRENT_TEST` env var to switch to `test_database.db`,
but this file is shared across parallel test runs and is never cleaned up
between test files, causing cross-contamination.

## Proposed Solution

1. Create `tests/conftest.py` with shared fixtures:
   - `tmp_db` — creates a unique temporary SQLite file per test session,
     sets `DW_DB_PATH`, calls `create_tables()`, and deletes the file on
     teardown.
   - `db_session` — yields a SQLAlchemy `Session` bound to `tmp_db`,
     rolls back after each test.
   - `seeded_db` — calls `seed_if_empty_sync` on top of `db_session`.
   - `client` — returns a FastAPI `TestClient` wired to the app with the
     `db_session` override for `get_db`.
2. Migrate existing test files to use these fixtures instead of their
   own ad-hoc setup.
3. Add `pytest.ini` (or a `[tool.pytest.ini_options]` section in a new
   `pyproject.toml`) with `testpaths = ["tests"]` and
   `asyncio_mode = "auto"`.

## Files Affected

- `tests/conftest.py` (new)
- `pytest.ini` or `pyproject.toml` (new)
- `tests/core/test_main.py` — refactor to use `client` fixture
- `tests/service/test_seed_data.py` — refactor to use `db_session`
- `tests/database/test_environment_logic.py` — refactor to use `tmp_db`

## Acceptance Criteria

- [ ] `pytest tests/` passes with no leftover `.db` files in the project
      root
- [ ] Running two pytest processes concurrently does not cause flaky
      failures
- [ ] Every test file imports zero database-setup boilerplate
- [ ] `pytest --co` shows all tests discovered under `tests/`

## Risks & Rollback

Existing tests may break if fixtures change session lifecycle. Migrate one
directory at a time and verify. Rollback: delete `conftest.py` and revert
individual test files.
