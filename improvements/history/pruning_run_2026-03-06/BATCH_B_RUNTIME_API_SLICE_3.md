# Batch B Runtime API Slice 3

Date: `2026-03-06`
Status: `completed`

## Scope
- Consolidate duplicated endpoint lock/delegation wiring into shared adapters.
- Preserve existing endpoint contracts and test patch seams.

## Changes
1. Added shared orchestration adapters:
- `src/api/game/orchestration_adapters.py`
  - `run_next_turn_orchestration(...)`
  - `run_action_turn_orchestration(...)`

2. Story endpoint delegation dedupe:
- `src/api/game/story.py`
  - `_resolve_next_turn` now delegates to `run_next_turn_orchestration(...)`
  - module-level symbols (`ensure_storylets`, `pick_storylet_enhanced`, etc.) retained and explicitly passed through to preserve patch-based tests.

3. Action endpoint delegation dedupe:
- `src/api/game/action.py`
  - `_resolve_freeform_action` now delegates to `run_action_turn_orchestration(...)`
  - module-level symbols (`get_spatial_navigator`, `pick_storylet_enhanced`, etc.) retained and explicitly passed through to preserve patch-based tests.

4. Unified turn endpoint delegation dedupe:
- `src/api/game/turn.py`
  - `/api/turn` now calls shared adapters for action/next branches instead of direct `TurnOrchestrator` calls.

## Guardrail Verification
Commands:
- `ruff check src/api/game/orchestration_adapters.py src/api/game/runtime_helpers.py src/api/game/story.py src/api/game/action.py src/api/game/turn.py`
- `pytest -q tests/api/test_story_endpoint.py tests/api/test_action_endpoint.py tests/api/test_turn_endpoint.py tests/api/test_game_endpoints.py`
- `python scripts/dev.py quality-strict`

Results:
- Lint: pass
- Targeted endpoint tests: `84 passed`
- Full strict gate: pass (`578 passed`; warning budget unchanged)

## Duplication Map Impact
Addressed item from `ORCHESTRATION_DUPLICATION_MAP.md`:
- Session lock + orchestrator delegation wrappers

Remaining notable runtime_api duplication candidate:
- Route-local SSE/phase event shaping in `action.py` (left intact due endpoint-contract sensitivity).
