# Add Alembic database migration system

## Problem

There is no migration system. `create_tables()` only runs
`Base.metadata.create_all(engine)`, which does nothing if tables already
exist. The vision requires adding new columns (`embedding` on `Storylet`,
timestamps) and new tables (`WorldEvent`). Without migrations, any schema
change requires manually dropping and recreating the database, losing all
content.

This blocks every other vision improvement that touches the data model.

## Proposed Solution

1. **Install Alembic** and add to `requirements.txt`.

2. **Initialize Alembic** with `alembic init alembic/` in the project root.

3. **Configure `alembic/env.py`** to:
   - Import `Base` from `src.database`
   - Import all models from `src.models`
   - Use the same `DW_DB_PATH` / `db_file` logic for the database URL
   - Support `--autogenerate` for schema diffing

4. **Create initial migration** that represents the current schema as the
   baseline (so existing databases can stamp themselves as "up to date"
   without re-creating tables).

5. **Update `main.py`** startup to run `alembic upgrade head` instead of
   (or in addition to) `create_tables()`, so the server auto-migrates on
   start.

6. **Document the workflow** in CLAUDE.md:
   ```bash
   # After changing a model
   alembic revision --autogenerate -m "add embedding column"
   alembic upgrade head
   ```

## Files Affected

- `requirements.txt` — add `alembic`
- `alembic/` — new directory (env.py, versions/)
- `alembic.ini` — new config file
- `main.py` — run migrations on startup
- `CLAUDE.md` — document migration workflow

## Acceptance Criteria

- [ ] `alembic upgrade head` creates tables from scratch on a fresh DB
- [ ] `alembic upgrade head` is a no-op on an already-current DB
- [ ] Adding a new column to a model and running autogenerate produces a
      valid migration
- [ ] `main.py` runs migrations on startup without manual intervention
- [ ] Existing databases can be stamped at the baseline without data loss
- [ ] CLAUDE.md documents the migration workflow

## Risks & Rollback

Low risk — Alembic is the standard SQLAlchemy migration tool. The main
risk is the initial migration conflicting with existing tables; the
`stamp` command handles this. Rollback: remove the `alembic/` directory
and revert to `create_tables()`.
