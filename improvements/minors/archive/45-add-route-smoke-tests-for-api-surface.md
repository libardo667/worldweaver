# Add route smoke tests for core API surface before and during refactors

## Problem

The refactor plan depends on preserving route existence and basic reachability, but there is no dedicated smoke suite that validates key endpoints at a lightweight level.

## Proposed Solution

1. Add a route smoke test module asserting status codes/reachability for:
   - `/health`
   - `/api/next`
   - `/api/action`
   - `/api/spatial/navigation/{session_id}`
   - `/api/spatial/move/{session_id}`
   - `/api/spatial/map`
   - `/api/spatial/assign-positions`
   - `/api/world/history`
   - `/api/world/facts?query=...`
   - `/author/suggest`
   - `/author/populate`
   - `/author/generate-world`
2. Keep assertions shallow (existence + status) to avoid brittle coupling.

## Files Affected

- `tests/api/test_route_smoke.py` (new)
- `tests/conftest.py` (if fixture adjustments are needed)

## Acceptance Criteria

- [ ] Smoke tests cover all listed endpoints.
- [ ] Tests fail when a route is accidentally unmounted or renamed.
- [ ] Smoke tests pass on current baseline.
