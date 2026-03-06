# Batch B Runtime API Slice 1

Date: `2026-03-06`
Status: `completed`

## Scope
- Consolidate duplicated endpoint wrapper logic in `src/api/game` without changing endpoint contracts.
- Remove one dead duplicated utility in endpoint layer (`semantic goal parsing` in `action.py`).

## Changes
1. Added shared helper module:
- `src/api/game/runtime_helpers.py`

2. Moved duplicate trace-id resolution into shared helper:
- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/api/game/turn.py`

3. Moved duplicate request timing/log envelope into shared helper:
- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/api/game/turn.py`

4. Removed unused semantic-goal duplicate from endpoint layer:
- removed `_SEMANTIC_GOAL_PATTERN` and `_extract_semantic_goal` from `src/api/game/action.py`
- canonical semantic-goal extraction remains in `src/services/turn_service.py`

## Guardrail Verification
Commands:
- `ruff check src/api/game/runtime_helpers.py src/api/game/story.py src/api/game/action.py src/api/game/turn.py`
- `pytest -q tests/api/test_action_endpoint.py tests/api/test_game_endpoints.py tests/api/test_route_smoke.py tests/api/test_trace_logging.py`

Results:
- Lint: pass
- Tests: `95 passed` (targeted API and trace coverage)

## Duplication Map Impact
Addressed items from `ORCHESTRATION_DUPLICATION_MAP.md`:
- Trace id resolution helpers
- Request timing log envelopes
- Semantic goal parsing duplication (endpoint-side copy)

Remaining high-value duplicate area for next slice:
- Prefetch scheduling wrapper blocks across `story.py`, `action.py`, `turn.py`
