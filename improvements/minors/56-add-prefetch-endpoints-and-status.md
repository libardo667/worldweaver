# Add a prefetch trigger endpoint and a cached frontier status response

## Problem
The client needs a simple, best-effort way to ask the server to prefetch the nearby frontier, and a way to confirm whether content is cached. Without this, prefetch can only be implicit and hard to debug.

## Proposed Solution
Add additive endpoints:
- `POST /api/prefetch/frontier`:
  - triggers a background prefetch job for the session,
  - returns `{ triggered: true }` even if prefetch is already warm.
- `GET /api/prefetch/status/{session_id}`:
  - returns `{ stubs_cached: int, expires_in_seconds: int }`.

These endpoints are additive and do not change existing routes.

## Files Affected
- `src/api/game/prefetch.py` (new router)
- `main.py` or `src/api/game/__init__.py` (include router)
- `src/services/prefetch_service.py` (if not already created)
- `tests/api/test_prefetch_endpoints.py` (new)

## Acceptance Criteria
- [ ] Prefetch endpoints exist and return stable JSON shapes.
- [ ] Trigger endpoint never blocks on LLM calls; it schedules and returns quickly.
- [ ] Status endpoint reports cached stub count and TTL remaining.
- [ ] `pytest -q` passes.
