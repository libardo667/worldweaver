# Add a /api/new-game endpoint for clean session initialisation

## Problem

There is no dedicated endpoint to start a fresh game. Currently a client
must call `/api/next` with a brand-new `session_id` and hope that the
default variable initialisation in `get_state_manager` (hardcoded defaults
like `"name": "Adventurer"`, `"has_pickaxe": True` in `game.py` lines
49-51) produces a playable starting state. There is no way for the client
to choose a starting location, set a player name, or receive an
introductory storylet — the first `/api/next` call just returns a random
eligible storylet with no narrative context.

This makes it impossible to build a polished "new game" experience for the
vertical slice.

## Proposed Solution

1. Add `POST /api/new-game` that:
   - Generates a `session_id` server-side (UUID4).
   - Accepts optional body: `{ "player_name": str, "starting_location": str }`.
   - Creates an `AdvancedStateManager` with clean defaults.
   - Persists the initial state to `session_vars`.
   - Finds or generates an introductory storylet (title contains "start",
     "begin", "introduction", or position `(0, 0)`).
   - Returns `{ "session_id", "text", "choices", "vars" }`.
2. Add a Pydantic schema `NewGameRequest` and `NewGameResponse` in
   `schemas.py`.
3. If no starting storylet exists, fall back to the seed center storylet
   or generate one via `llm_service.generate_starting_storylet`.

## Files Affected

- `src/api/game.py` — new endpoint
- `src/models/schemas.py` — new request/response models
- `tests/api/test_game_endpoints.py` — tests for the new endpoint

## Acceptance Criteria

- [ ] `POST /api/new-game` returns a valid session with an introductory
      storylet
- [ ] `player_name` is stored in session vars and rendered into storylet
      text
- [ ] Calling `/api/next` with the returned `session_id` continues the
      game normally
- [ ] Missing starting storylet triggers fallback, not a 500 error
- [ ] At least 3 tests cover happy path, custom name, and missing
      storylet fallback

## Risks & Rollback

Additive endpoint — no existing behaviour changes. Delete the endpoint
and schema to roll back.
