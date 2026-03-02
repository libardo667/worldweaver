# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WorldWeaver is a **narrative simulation engine** — a living world where AI generates storylets that fire based on semantic proximity to the player's context, and once experienced, become permanent world facts that reshape what happens next. Think Dwarf Fortress meets text adventure: you're not watching from above, you're in the world. The full vision is in `specs/VISION.md`.

Currently implemented as a Python/FastAPI backend managing storylets (narrative units with conditions, choices, and spatial positions), session state, and OpenAI-powered content generation. The architecture is evolving from hard-coded requirement matching toward semantic embedding + probability-based storylet selection, and from a pure 2D spatial grid toward a dual-layer model (physical geography + semantic narrative space).

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the dev server
uvicorn main:app --reload

# Run all tests
pytest tests/ -q

# Run a single test file
pytest tests/core/test_main.py -q

# Run a specific test function
pytest tests/api/test_author_validation.py::test_function_name -v

# Run tests by category using the test runner
python run_true_tests.py           # all categories
python run_true_tests.py core      # core tests only
python run_true_tests.py api       # API tests only
python run_true_tests.py database  # database tests
python run_true_tests.py service   # service tests

# Database utilities
python db/fresh_database.py        # reset database
python db/view_database.py         # inspect database contents
python db/storylet_map.py          # visualize storylet spatial layout
```

There is no linter or formatter configured in the project (black, flake8, mypy are commented out in requirements.txt).

## Architecture

### Entry Point & API Layer

`main.py` creates the FastAPI app with two routers:
- **Game API** (`src/api/game.py`, prefix `/api`) — Player-facing: get next storylet, make choices, spatial navigation (move, get map, compass directions)
- **Author API** (`src/api/author.py`, prefix `/author`) — Content management: CRUD storylets, AI generation, world building, auto-improvement triggers

### Service Layer (`src/services/`)

- **`game_logic.py`** — Core storylet selection (`pick_storylet`), template rendering with `SafeDict` for missing keys, requirement matching with comparison operators (gte, lte, gt, lt, eq, ne)
- **`state_manager.py`** — `AdvancedStateManager` class tracking per-session variables, inventory (with item states/properties), NPC relationships, and environment state. Supports state history and rollback
- **`spatial_navigator.py`** — `SpatialNavigator` manages 2D grid positions for storylets, 8-directional movement, coordinate assignment via `auto_assign_coordinates()` static method. Uses `LocationMapper` for semantic name-to-coordinate mapping
- **`llm_service.py`** — OpenAI integration for storylet generation, contextual generation based on game state, fallback logic on timeout/failure
- **`auto_improvement.py`** — Orchestrates post-creation storylet improvement (smoothing + deepening)
- **`story_smoother.py`** — Graph analysis to fix isolated locations, dead-end variables, missing bidirectional paths
- **`story_deepener.py`** — Narrative flow enhancement, bridge storylets between abrupt transitions, choice preview annotations
- **`storylet_analyzer.py`** — Gap analysis and content recommendations
- **`location_mapper.py`** — Semantic mapping of location names to spatial coordinates
- **`seed_data.py`** — Database seeding with starter storylets at all 8 compass directions plus center

### Data Models

- **`src/models/__init__.py`** — SQLAlchemy models: `Storylet` (title unique, text_template, requires JSON, choices JSON, weight, position JSON with x/y) and `SessionVars` (session_id PK, vars JSON)
- **`src/models/schemas.py`** — Pydantic request/response models. `StoryletIn` normalizes both `{label, set}` and `{text, set_vars}` choice formats via a field validator
- **`src/database.py`** — SQLite via SQLAlchemy. Database path controlled by `DW_DB_PATH` env var; defaults to `test_database.db` under pytest, `worldweaver.db` otherwise

### Key Data Flow

1. Author creates storylets → saved to DB → `SpatialNavigator.auto_assign_coordinates()` assigns positions → `auto_improve_storylets()` runs smoothing/deepening
2. Player requests next storylet → `pick_storylet` filters by requirements against session vars → weighted random selection → template rendered with session vars
3. Player navigates → `SpatialNavigator` resolves direction to coordinate delta → finds storylets at target position

### In-Memory Caches

`src/api/game.py` holds `_state_managers` and `_spatial_navigators` dicts keyed by session/db ID. These are not persistent across restarts.

### Tests (`tests/`)

Organized into: `api/`, `contract/`, `core/`, `database/`, `diagnostic/`, `integration/`, `service/`. No conftest.py or pytest configuration file exists — pytest discovers tests by convention. The database module auto-switches to `test_database.db` when `PYTEST_CURRENT_TEST` env var is set (handled by pytest automatically).

### Specs & Planning

`specs/` contains architecture and API contract specifications. `tasks/backlog.md` tracks the full task backlog. `plan.json` holds the structured project plan. `memory/constitution.md` defines project values and workflow conventions.

## Environment

- Python >= 3.11
- Requires `OPENAI_API_KEY` in `.env` file for LLM features
- SQLite database (no external DB server needed)
- `DW_DB_PATH` env var overrides the default database file path
