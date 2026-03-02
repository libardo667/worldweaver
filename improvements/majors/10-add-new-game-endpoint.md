# Add a /api/new-game endpoint with starting goal

## Problem

There is no dedicated endpoint to start a fresh game. Currently a client
must call `/api/next` with a brand-new `session_id` and hope that the
default variable initialisation in `get_state_manager` produces a playable
starting state. There is no way for the client to set a player name,
choose a starting location, or — critically for the vision — specify a
**starting goal** that seeds the player's initial semantic context.

The vision says: "You start with a simple goal (deliver a package, find a
missing person, survive the winter)." That goal needs to be captured at
game start and used to seed the initial probability field for storylet
selection.

## Proposed Solution

1. Add `POST /api/new-game` that:
   - Generates a `session_id` server-side (UUID4).
   - Accepts body: `{ "player_name": str, "starting_goal": str, "starting_location": str? }`.
   - Creates an `AdvancedStateManager` with clean defaults + the goal/name.
   - Stores `starting_goal` in session vars (used later by the semantic
     selection engine to compute the player's initial context vector).
   - Persists the initial state to `session_vars`.
   - Finds or generates an introductory storylet contextualised to the goal.
   - Returns `{ "session_id", "text", "choices", "vars" }`.
2. Add Pydantic schemas `NewGameRequest` and `NewGameResponse` in `schemas.py`.
3. If no starting storylet exists, generate one via
   `llm_service.generate_starting_storylet` using the goal as context.

## Files Affected

- `src/api/game.py` — new endpoint
- `src/models/schemas.py` — new request/response models
- `tests/api/test_game_endpoints.py` — tests for the new endpoint

## Acceptance Criteria

- [ ] `POST /api/new-game` returns a valid session with an introductory storylet
- [ ] `starting_goal` is stored in session vars
- [ ] `player_name` is stored in session vars and rendered into storylet text
- [ ] Calling `/api/next` with the returned `session_id` continues the game normally
- [ ] Missing starting storylet triggers LLM generation or fallback, not a 500 error
- [ ] At least 3 tests cover happy path, custom goal/name, and missing storylet fallback

## Risks & Rollback

Additive endpoint — no existing behaviour changes. Delete the endpoint
and schema to roll back.
