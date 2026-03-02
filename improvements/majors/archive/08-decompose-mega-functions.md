# Decompose mega-functions into single-responsibility units

## Problem

Several functions do far too much, making them hard to test, debug, and
extend:

1. **`save_storylets_with_postprocessing`** (`src/api/author.py` lines
   25-127) — handles duplicate detection, DB insert, spatial assignment,
   and auto-improvement triggering in a single 100-line function.
2. **`pick_storylet`** (`src/services/game_logic.py` lines 54-119) —
   queries all storylets, filters eligibility, triggers LLM generation as
   a side effect, calls auto-improvement, and finally picks one.
3. **`get_spatial_navigation`** (`src/api/game.py` lines 293-375) — loads
   positions, computes directions, checks accessibility, and formats the
   response all inline.

Each of these is difficult to unit-test because the function does five
things and mocking any one part requires understanding all the others.

## Proposed Solution

### `save_storylets_with_postprocessing` → 3 functions

- `deduplicate_storylets(db, storylets) -> list` — returns only new
  storylets (skip duplicates).
- `insert_storylets(db, storylets) -> list[int]` — bulk insert and return
  IDs.
- `postprocess_storylets(db, ids, trigger) -> dict` — spatial assignment +
  auto-improvement. The existing function becomes a thin orchestrator
  calling these three.

### `pick_storylet` → 2 functions

- `pick_storylet(db, vars) -> Storylet | None` — pure selection from
  existing eligible storylets (no side effects).
- `ensure_storylets(db, vars, min_count)` — calls LLM generation +
  auto-improvement if eligible count is below threshold. Called by the
  `/api/next` handler *before* `pick_storylet`.

### `get_spatial_navigation` → helper

- Extract direction computation into
  `SpatialNavigator.get_navigation_options(position, session_vars)` so the
  endpoint handler only does request/response mapping.

## Files Affected

- `src/api/author.py`
- `src/services/game_logic.py`
- `src/api/game.py`
- `src/services/spatial_navigator.py`

## Acceptance Criteria

- [ ] No function exceeds 40 lines (excluding docstrings)
- [ ] `pick_storylet` has no LLM side effects
- [ ] Each extracted function has at least one unit test
- [ ] All existing API behaviour is unchanged (integration tests pass)

## Risks & Rollback

Internal refactor only — the API surface is unchanged. If integration tests
break, the decomposition was incorrect; revert the individual file.
