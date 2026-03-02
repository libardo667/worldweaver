# Add a session bootstrap endpoint with initial goal payload

## Problem

Starting sessions currently depends on callers manually coordinating `session_id` and initial vars. There is no single bootstrap endpoint that captures the player's initial goal and seed context.

## Proposed Solution

1. Add `POST /api/session/bootstrap` returning a new `session_id` plus initialized state.
2. Accept optional initial goal text and starting location/theme hints.
3. Persist bootstrap metadata in session vars for immediate selector use.

## Files Affected

- `src/api/game.py`
- `src/models/schemas.py`
- `src/services/state_manager.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [ ] Endpoint returns a valid `session_id` and initialized state payload.
- [ ] Provided initial goal is persisted and visible in state summary.
- [ ] Existing `/api/next` flows continue working for manually created sessions.
