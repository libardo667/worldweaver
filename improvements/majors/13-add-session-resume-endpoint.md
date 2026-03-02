# Add GET /api/state/{session_id} for session resume

## Problem

Sessions are lost on page reload because there is no API endpoint to
check whether a session still exists or retrieve its current state. The
old improvement (13-persist-twine-session-across-reloads) was Twine-specific;
this reframes it as a backend API task that any frontend can use.

Without session resume, every page reload creates a new session, losing
all player progress — variables, inventory, relationships, spatial
position, and (under the vision) the entire accumulated world memory.

## Proposed Solution

1. Add `GET /api/state/{session_id}` that:
   - Looks up the session in `session_vars`.
   - If found, returns the full state (vars, inventory, relationships,
     environment, current position).
   - If not found, returns 404 with `{"detail": "Session not found"}`.
2. Add `DELETE /api/state/{session_id}` for explicit session teardown.
3. Add Pydantic `SessionStateResponse` schema.
4. Document that clients should persist the `session_id` (in localStorage,
   a cookie, or whatever is appropriate for their platform) and call
   this endpoint on startup to resume.

## Files Affected

- `src/api/game.py` — two new endpoints
- `src/models/schemas.py` — new response model
- `tests/api/test_game_endpoints.py` — tests for resume + teardown

## Acceptance Criteria

- [ ] `GET /api/state/{session_id}` returns full state for existing sessions
- [ ] `GET /api/state/{session_id}` returns 404 for unknown sessions
- [ ] `DELETE /api/state/{session_id}` removes the session and returns 204
- [ ] State returned includes vars, inventory summary, and current position
- [ ] At least 3 tests: happy path resume, 404 for missing, delete + verify gone

## Risks & Rollback

Additive endpoints — no existing behaviour changes. Delete the endpoints
and schema to roll back.
