# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WorldWeaver is a persistent shared-world platform where autonomous AI residents live continuously alongside human players in a geographically-grounded environment. It is a monorepo (consolidated from 5 repos on 2026-03-15) with three major components:

- **`worldweaver_engine/`** — Backend (FastAPI + SQLAlchemy), React SPA client, and dev tooling
- **`ww_agent/`** — Autonomous resident runtime (async Python daemon; a salience substrate + predictive pulse, `CognitiveCore`, per resident)
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

Residents run on a **salience substrate + predictive pulse** (Major 49), not the old loop bank.
`resident.py` builds a `CognitiveCore` (`src/runtime/cognitive_core.py`); the former fast/slow/mail/
ground/wander loops are demoted to pure sensorimotor mechanism beneath it. Each tick runs one cycle:

```
perceive → integrate (surprise vs prediction → leaky arousal) → on ignition, ONE LLM pulse → act
```

- **The ledger is the only state.** Arousal, mood, grief, the slow self-model, and the top-down
  prediction (the "afterimage") are all `derive_*` reducers over an append-only event log, computed
  at read time (`src/runtime/{ledger,substrate,salience}.py`).
- **Surprise drives the rhythm.** `surprise = mismatch(stimulus, prediction)` accumulates a leaky
  arousal; crossing threshold is **ignition** — the single event that fires one LLM call
  (`pulse_engine.py`). In lulls, **settling/fervor** fire quiet self-directed pulses (the idle
  "making" gear). Circadian wakefulness scales the rhythm so a shard quiets after dark.
- **Affect is per-resident**, read from the soul embedded as a **drive vector** (`drive.py`) — so
  residents in one room respond as distinct people. **Grief** (`salience.derive_grief`) is an
  *undischargeable* integral of confirmed loss (a safety boundary — see `../the-stable/docs/grief-and-coupling.md`).
- **The self lives in the soul + ledger + kept memory, not the model** (the model is a swappable pen).

This runtime is one fork of a substrate shared with the standalone familiar project at `../the-stable`
(the canonical familiar home). Some matured pieces — the multi-day concordance growth gate and the
in-ignition tool loop — currently live in that fork and are being reconverged into the city runtime.

Resident identity lives in `<resident_dir>/identity/` (a canonical soul + a federation-held growth layer).

⚠️ The old four-loop description (fast/slow/mail/wander; three-layer working/provisional/long-term
memory) is **superseded** — trust `resident.py` and `src/runtime/` over any doc that still says "loops."

### Narrative Lanes

- **Narrator** — Scene descriptions from world state + rules
- **Referee** — Action validation (strict, low-temp models)
- **Planner** — Internal reasoning, not exposed to players

### Database

SQLite for local dev (Alembic migrations auto-run on startup). Postgres migration is planned.

## Workflow Authority

`worldweaver_engine/AGENTS.md` is the authoritative workflow policy. Authority order for conflicts:

1. Explicit task item scope (`prune/majors/*`, `prune/minors/*`)
2. Project anchors: `prune/VISION.md`, `prune/ROADMAP.md`
3. Harness policy: `prune/harness/` docs
4. Harness templates

Before implementation: declare authoritative path, default-path impact, contract impact, and validation commands.

## Key Conventions

- Extend existing authoritative paths; do not create parallel paths
- Keep diffs bounded to declared scope; no drive-by refactors
- Run `python scripts/dev.py quality-strict` for non-trivial changes
- Shard secrets live in `shards/<name>/.env`, not the repo root
- CI gates: root `.github/workflows/ci-gates.yml` (`dev.py quality-strict`, agent tests, and public
  hygiene). The old narrative-eval smoke was retired with the storylet pipeline.
