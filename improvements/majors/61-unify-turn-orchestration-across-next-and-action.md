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

## Files Affected

- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/api/game/__init__.py`
- `src/models/schemas.py`
- `src/services/turn_service.py` (new)
- `tests/api/test_game_endpoints.py`
- `tests/api/test_action_endpoint.py`
- `tests/api/test_turn_endpoint.py` (new)

## Acceptance Criteria

- [ ] `/api/next` and `/api/action` both execute through shared turn-phase
      orchestration logic.
- [ ] Shared sequencing enforces one commit order for reducer, tick, selection,
      and persistence.
- [ ] Optional `/api/turn` can serve unified clients without breaking legacy
      routes.
- [ ] Existing endpoint payload contracts remain stable for current clients.
- [ ] Route/integration tests for next/action continue to pass.

## Risks & Rollback

Risk: orchestration refactor can introduce subtle behavioral regressions across
both major gameplay endpoints.

Rollback:

1. Keep old route internals behind a feature flag until parity tests pass.
2. Roll back to legacy handlers if sequencing regressions are found.
3. Maintain side-by-side telemetry during rollout to compare old/new paths.

