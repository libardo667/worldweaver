# Batch B Runtime API Slice 2

Date: `2026-03-06`
Status: `completed`

## Scope
- Consolidate duplicated endpoint-layer prefetch scheduling wrappers in `src/api/game`.
- Keep endpoint contracts and module-level patch points unchanged.

## Changes
1. Extended shared helper module:
- `src/api/game/runtime_helpers.py`
  - `record_timing_ms(...)`
  - `schedule_prefetch_async_best_effort(...)`
  - `schedule_prefetch_sync_best_effort(...)`

2. Replaced duplicated async prefetch wrappers:
- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/api/game/action.py` (`/api/action/stream` path)

3. Replaced duplicated sync prefetch wrappers:
- `src/api/game/turn.py`

4. Kept existing test patch seams:
- `run_inference_thread` still called from each endpoint module via injected function parameter.
- `schedule_frontier_prefetch` still imported and passed from each endpoint module.

## Guardrail Verification
Commands:
- `ruff check src/api/game/runtime_helpers.py src/api/game/story.py src/api/game/action.py src/api/game/turn.py`
- `pytest -q tests/api/test_story_endpoint.py tests/api/test_action_endpoint.py tests/api/test_game_endpoints.py tests/api/test_turn_endpoint.py`
- `python scripts/dev.py quality-strict`

Results:
- Lint: pass
- Targeted endpoint tests: `84 passed`
- Full strict gate: pass (`578 passed`; warning budget unchanged)

## Duplication Map Impact
Addressed items from `ORCHESTRATION_DUPLICATION_MAP.md`:
- Prefetch scheduling blocks

Remaining notable runtime_api duplication candidate:
- Session lock + orchestrator delegation wrappers in endpoint modules (low churn but still repeated).
