# Unify turn orchestration across `/api/next` and `/api/action` with one authoritative turn pipeline

## Problem

Turn processing logic is split across separate endpoints with overlapping but
different sequencing rules (`src/api/game/story.py` and
`src/api/game/action.py`). This increases the risk of inconsistent commit order
(state mutation, event recording, selection, prefetch, and optional simulation
tick).

## Proposed Solution

Add one turn orchestration service and route both endpoints through it:

1. Introduce a `turn_service` pipeline that standardizes turn phases:
   - ingest intent,
   - reduce/commit event,
   - run simulation tick,
   - select/generate next content,
   - persist/emit response.
2. Keep `/api/next` and `/api/action` as compatibility entrypoints, but delegate
   core sequencing to the shared turn service.
3. Add optional `/api/turn` endpoint for unified clients (feature-flagged),
   while preserving existing endpoint contracts.
4. Ensure idempotency behavior is preserved for freeform actions.

## Scope Boundaries

- Keep `/api/next` and `/api/action` request/response contracts unchanged.
- Keep streaming `/api/action/stream` contract unchanged.
- Limit new API surface to optional `/api/turn` only.

## Assumptions

- Existing reducer and simulation tick systems remain authoritative for state mutation.
- Existing route-level tracing/metrics/prefetch behavior should remain visible and stable.
- Unified `/api/turn` can be gated behind a runtime feature flag and default disabled.

## Files Affected

- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/api/game/__init__.py`
- `src/models/schemas.py`
- `src/services/turn_service.py` (new)
- `src/api/game/turn.py` (new)
- `src/config.py`
- `tests/api/test_game_endpoints.py`
- `tests/api/test_action_endpoint.py`
- `tests/api/test_turn_endpoint.py` (new)

## Validation Commands

- `python -m pytest tests/api/test_game_endpoints.py tests/api/test_action_endpoint.py tests/api/test_turn_endpoint.py -q`
- `python -m pytest -q`
- `npm --prefix client run build`

## Acceptance Criteria

- [x] `/api/next` and `/api/action` both execute through shared turn-phase
      orchestration logic.
- [x] Shared sequencing enforces one commit order for reducer, tick, selection,
      and persistence.
- [x] Optional `/api/turn` can serve unified clients without breaking legacy
      routes.
- [x] Existing endpoint payload contracts remain stable for current clients.
- [x] Route/integration tests for next/action continue to pass.

## Risks & Rollback

Risk: orchestration refactor can introduce subtle behavioral regressions across
both major gameplay endpoints.

Rollback:

1. Keep old route internals behind a feature flag until parity tests pass.
2. Disable `/api/turn` immediately via `WW_ENABLE_TURN_ENDPOINT=0`.
3. Roll back `turn_service` delegation commits if sequencing regressions are found.
