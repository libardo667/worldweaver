# Add integration tests for core game endpoints

## Problem

The player-facing game API has **zero** integration tests. The `/api/next`
endpoint — the most important endpoint in the entire application — has no
test coverage. Neither do the state mutation endpoints
(`/api/state/{session_id}/relationship`, `.../item`, `.../environment`) or
the state summary endpoint (`/api/state/{session_id}`). This means any
refactor to game logic can silently break the core gameplay loop with no
safety net.

## Proposed Solution

Create `tests/api/test_game_endpoints.py` using the FastAPI `TestClient`
(already available via `httpx`). Tests should cover:

1. **`/api/next`** — happy path with seeded storylets, requirement filtering
   (eligible vs ineligible storylets), weighted selection distribution,
   session variable persistence across calls.
2. **`/api/state/{session_id}`** — verify summary structure, unknown session
   handling.
3. **`/api/state/{session_id}/relationship`** — create/update/read NPC
   relationship.
4. **`/api/state/{session_id}/item`** — add/modify/remove inventory item.
5. **`/api/state/{session_id}/environment`** — update weather, time, danger.
6. **`/api/cleanup-sessions`** — verify stale sessions are removed and fresh
   sessions are kept.

All tests should use `DW_DB_PATH` pointed at a temp file to isolate from
production data.

## Files Affected

- `tests/api/test_game_endpoints.py` (new)
- `tests/conftest.py` (new — shared fixtures for TestClient and temp DB)

## Acceptance Criteria

- [ ] At least 20 test functions covering the 6 endpoint groups above
- [ ] `pytest tests/api/test_game_endpoints.py` passes in CI with no
      external dependencies (no OpenAI key required)
- [ ] Tests run in < 10 seconds
- [ ] No test modifies the production database

## Risks & Rollback

Pure additive — no production code changes. Delete the file to roll back.
