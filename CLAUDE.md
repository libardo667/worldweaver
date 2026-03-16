# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WorldWeaver is a persistent shared-world platform where autonomous AI residents live continuously alongside human players in a geographically-grounded environment. It is a monorepo (consolidated from 5 repos on 2026-03-15) with three major components:

- **`worldweaver_engine/`** — Backend (FastAPI + SQLAlchemy), React SPA client, and dev tooling
- **`ww_agent/`** — Autonomous resident runtime (async Python daemon, 4 cognitive loops per resident)
- **`shards/`** — Per-city shard instances (`ww_sfo`, `ww_pdx`, `ww_world` federation root)

## Commands

All commands run from the `worldweaver_engine/` directory using the canonical dev harness:

```bash
# Setup
python scripts/dev.py install              # Install all backend + frontend deps

# Run
python scripts/dev.py weave-up --city ww_sfo    # Start full stack (Docker Compose)
python scripts/dev.py weave-down --city ww_sfo   # Stop stack
python scripts/dev.py backend                     # Backend only (uvicorn :8000)
python scripts/dev.py client                      # Client only (vite :5173)

# Test
python scripts/dev.py test                        # Run pytest suite
python scripts/dev.py quality-strict              # Full CI-equivalent validation
python scripts/dev.py pytest-warning-budget       # Tests with warning budget enforcement

# Single test file
cd worldweaver_engine && python -m pytest tests/api/test_settings_readiness.py -v

# Lint
python scripts/dev.py lint-all                    # ruff + black
python scripts/dev.py gate3-strict                # CI gate 3: static checks
```

For `ww_agent/` tests: `cd ww_agent && python -m pytest tests/ -v`

## Code Style

- Python 3.11+ (backend), Python 3.12+ (agent)
- Line length: **320** for both ruff and black
- Ruff rules: E, F only
- asyncio_mode = "auto" in pytest (no need for `@pytest.mark.asyncio`)
- TypeScript/React frontend with Vite

## Architecture

### Shard-First Runtime

Each city runs as an independent shard with its own backend, database, agents, and `.env`. The federation root (`ww_world`, port 9000) coordinates inter-shard travel. City shards (`ww_sfo` port 8002, `ww_pdx` port 8003) register via a federation pulse loop. Shared `FEDERATION_TOKEN` authenticates cross-shard requests.

### Backend Structure (`worldweaver_engine/src/`)

- `api/` — FastAPI routes: `game/` (gameplay), `auth/` (JWT auth), `federation/` (shard coordination)
- `services/` — Business logic: `state/` (world state), `simulation/` (turn resolution), `rules/` (action validation), `llm_client.py`, `federation_pulse.py`
- `core/` — Base classes, reducers, narrative primitives
- `models/` — SQLAlchemy ORM models
- `config.py` — Pydantic-settings configuration

### Agent Cognitive Architecture (`ww_agent/src/`)

Residents run four parallel async loops:
- **Fast loop** — Event-driven, classifier → 8 handlers, 120s cooldown
- **Slow loop** — Deliberate reflection, impression processing, SOUL.md updates
- **Mail loop** — Asynchronous correspondence (cannot make world actions — enforced in code)
- **Wander loop** — Multi-hop navigation

Three-layer memory: working (`working.json`), provisional (`provisional/`), long-term (`long_term/`)

Resident identity lives in `residents/<name>/identity/SOUL.md`.

### Narrative Lanes

- **Narrator** — Scene descriptions from world state + rules
- **Referee** — Action validation (strict, low-temp models)
- **Planner** — Internal reasoning, not exposed to players

### Database

SQLite for local dev (Alembic migrations auto-run on startup). Postgres migration is planned.

## Workflow Authority

`worldweaver_engine/AGENTS.md` is the authoritative workflow policy. Authority order for conflicts:

1. Explicit task item scope (`improvements/majors/*`, `improvements/minors/*`)
2. Project anchors: `improvements/VISION.md`, `improvements/ROADMAP.md`
3. Harness policy: `improvements/harness/` docs
4. Harness templates

Before implementation: declare authoritative path, default-path impact, contract impact, and validation commands.

## Key Conventions

- Extend existing authoritative paths; do not create parallel paths
- Keep diffs bounded to declared scope; no drive-by refactors
- Run `python scripts/dev.py quality-strict` for non-trivial changes
- Shard secrets live in `shards/<name>/.env`, not the repo root
- CI gates: `ci-gates.yml` (gate3-strict + pytest-warning-budget) and `narrative-eval-smoke.yml`
