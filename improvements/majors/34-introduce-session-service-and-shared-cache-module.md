# Introduce a session service and shared cache module for state persistence

## Problem

`src/api/game.py` currently owns:
- state manager lifecycle,
- cache implementation (`_TTLCacheMap`),
- DB round-trip logic for session persistence,
- current-location resolution.

This makes the router stateful and difficult to reason about or reuse in subrouters.

## Proposed Solution

1. Create `src/services/cache.py` and move `_TTLCacheMap` there.
2. Create `src/services/session_service.py` with:
   - `get_state_manager(session_id, db) -> AdvancedStateManager`
   - `save_state(state_manager, db) -> None`
   - `resolve_current_location(state_manager, db) -> str`
3. Preserve existing cache keying strategy, TTL, and max-size configuration.
4. Update `src/api/game.py` to delegate all session/caching responsibilities to `session_service`.
5. Keep `/api/cleanup-sessions` behavior and cache cleanup semantics unchanged.

## Files Affected

- `src/services/cache.py` (new)
- `src/services/session_service.py` (new)
- `src/api/game.py`
- `tests/api/test_game_cache_cleanup.py`
- `tests/integration/test_session_persistence.py`
- `tests/service/test_session_service.py` (new)

## Acceptance Criteria

- [ ] Session load/save behavior is unchanged for v1/v2 stored state payloads.
- [ ] Cache entries still expire and evict with existing config values.
- [ ] Cleanup endpoint still removes stale DB sessions and matching cache entries.
- [ ] Router-level state/caching logic is removed from `src/api/game.py`.
- [ ] `pytest -q` passes.

## Risks & Rollback

Risk is cache behavior drift leading to stale or missing state managers. Roll back by restoring cache and session helper functions in `src/api/game.py` and removing the extracted modules.
