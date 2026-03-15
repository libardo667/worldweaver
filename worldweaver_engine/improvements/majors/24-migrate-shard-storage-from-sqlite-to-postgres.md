# Migrate shard storage from SQLite to Postgres

## Problem

The shard-first runtime has outgrown SQLite as its primary operational database.

Concrete issues visible in the current system:

- City shards and the federation root are long-running multi-container services with
  ongoing reads and writes from backends, agents, pulse loops, onboarding, chat, and
  world-event recording.
- On the current Windows-hosted bind-mounted runtime path, SQLite WAL mode is proving
  fragile enough to produce malformed shard database files during normal development
  and restore cycles.
- Operational backups and restores are too easy to do unsafely when the runtime is a
  live SQLite file plus WAL sidecars rather than a proper service.
- The product is becoming more concurrent and more infrastructure-like:
  - human auth and actor identity
  - portable BYOK secrets
  - city federation
  - growing resident counts
  - more continuous agent runtime
- Even if moving to WSL reduces the worst filesystem-pathology risk, SQLite remains a
  poor long-term fit for steward-run shards and federation-root services.

At this point, storage reliability is an architecture issue, not just a local-dev
paper cut.

## Proposed Solution

Move shard storage from file-backed SQLite to Postgres, while preserving the current
one-database-per-shard federation model.

This migration should keep the logical architecture the same:

- `ww_world` keeps its own database
- `ww_sfo` keeps its own database
- `ww_pdx` keeps its own database

The change is the storage engine and connection model, not a collapse into one shared DB.

### Phase 1 - Make database configuration URL-driven

- Replace SQLite-path-first assumptions with a canonical database URL contract.
- Add a setting such as:
  - `WW_DATABASE_URL`
- Keep `WW_DB_PATH` as a temporary compatibility path for SQLite during migration.
- Update engine creation, Alembic environment, scripts, and tests so they can resolve:
  - Postgres URLs
  - SQLite fallback only where explicitly intended

### Phase 2 - Local shard Postgres services

- Add Postgres services for local shard development:
  - one DB container or logical DB per shard
  - `ww_world`
  - `ww_sfo`
  - `ww_pdx`
- Update shard Compose templates and `new_shard.py` so fresh shards can be generated
  Postgres-first rather than SQLite-first.
- Add clear env ownership for:
  - database host
  - database port
  - database name
  - database user
  - database password

### Phase 3 - Application and migration compatibility

- Update SQLAlchemy and Alembic setup to support both SQLite and Postgres during the
  transition window.
- Remove SQLite-specific migration assumptions where possible, especially:
  - batch-only ALTER patterns that exist solely for SQLite
  - path-derived database URL logic
  - maintenance scripts that directly manipulate `sqlite_sequence`
- Verify all existing model tables work cleanly on Postgres, including:
  - `session_vars`
  - `players`
  - federation tables
  - world graph tables
  - chat / DM tables
  - projection tables

### Phase 4 - Data migration and shard cutover

- Provide a repeatable migration path from existing SQLite shard DBs into Postgres:
  - schema creation via Alembic
  - export/import or application-level migration scripts
- Perform cutover shard by shard:
  - `ww_world` first
  - `ww_sfo` next
  - `ww_pdx` next
- Add validation checks before each cutover:
  - row counts
  - auth records
  - federation rows
  - world node / edge counts
  - session bootstrap sanity

### Phase 5 - Operational tooling

- Add safe backup and restore scripts for Postgres-backed shards.
- Update operator docs to describe:
  - local dumps
  - restore workflow
  - migration rollback
  - how to inspect shard DB state safely
- Make WSL-first local runtime the canonical baseline for Postgres-backed shard dev.

## Files Affected

- `worldweaver_engine/src/database.py`
- `worldweaver_engine/alembic/env.py`
- `worldweaver_engine/alembic/versions/*`
- `worldweaver_engine/src/config.py`
- `worldweaver_engine/main.py`
- `worldweaver_engine/scripts/dev.py`
- `worldweaver_engine/scripts/new_shard.py`
- `worldweaver_engine/scripts/seed_world.py`
- `worldweaver_engine/scripts/canon_reset.py`
- `worldweaver_engine/scripts/repair_graph.py`
- `worldweaver_engine/scripts/patch_colliding_nodes.py`
- `worldweaver_engine/tests/conftest.py`
- `worldweaver_engine/tests/database/test_environment_logic.py`
- `worldweaver_engine/README.md`
- `worldweaver_engine/FEDERATION.md`
- `worldweaver_engine/improvements/WSL_RUNTIME_GUIDE.md`
- `shards/ww_world/docker-compose.yml`
- `shards/ww_sfo/docker-compose.yml`
- `shards/ww_pdx/docker-compose.yml`
- `shards/_template/*` or equivalent shard-generation template files

## Acceptance Criteria

- [ ] The backend can run against Postgres using a canonical database URL without relying on SQLite path logic
- [ ] `ww_world`, `ww_sfo`, and `ww_pdx` each run successfully against Postgres in local shard-first development
- [ ] Alembic migrations run cleanly against Postgres-backed shard databases
- [ ] Existing shard data can be migrated from SQLite into Postgres with a documented, repeatable process
- [ ] Auth, actor identity, world events, chat, DMs, and federation tables behave correctly after migration
- [ ] Shard generation templates can produce Postgres-ready shard configs by default
- [ ] Backup and restore workflows are documented and safer than raw live SQLite file copies
- [ ] WSL-first local runtime is documented as the canonical environment for the Postgres-backed stack
- [ ] SQLite can remain as an explicitly limited compatibility mode during migration, but not as the only supported live runtime path

## Risks & Rollback

- Database-engine migrations touch almost every operational workflow. If done too broadly in one pass,
  the failure surface will be large. Cut over shard by shard.
- SQLite-specific scripts and tests may silently encode assumptions that only break after the move.
  Audit scripts and environment resolution carefully.
- Copying malformed SQLite state into Postgres would only preserve bad data more reliably. Validate
  source shard integrity before migration.
- Rollback path: keep the SQLite compatibility path available during the transition, cut over one shard
  at a time, and keep exportable backups of the last clean pre-Postgres state before each shard switch.
