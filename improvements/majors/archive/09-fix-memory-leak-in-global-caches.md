# Fix memory leak in global state-manager and navigator caches

## Problem

`src/api/game.py` lines 22-23 maintain two module-level dicts:

```python
_state_managers: Dict[str, AdvancedStateManager] = {}
_spatial_navigators: Dict[str, SpatialNavigator] = {}
```

Every new session adds an entry to `_state_managers` and it is **never
removed** unless `/api/cleanup-sessions` is called manually. Over hours of
traffic the process will consume unbounded memory. The navigator cache is
keyed by `id(db)`, which is the memory address of the SQLAlchemy session
object — these addresses get reused by the Python allocator, so the cache
can silently serve stale navigators for different sessions.

## Proposed Solution

1. Replace the plain dicts with an LRU cache (stdlib `functools.lru_cache`
   or a `cachetools.TTLCache`) with a configurable max size (default 500)
   and TTL (default 1 hour).
2. Change the navigator cache key from `id(db)` to a stable identifier
   (e.g., the database file path from `src/database.py`).
3. Wire `/api/cleanup-sessions` to also evict corresponding cache entries.
4. Add a startup log line showing the cache configuration.

## Files Affected

- `src/api/game.py` — replace dicts with TTL cache, fix navigator key
- `requirements.txt` — add `cachetools` (or use stdlib LRU + manual TTL)

## Acceptance Criteria

- [ ] After 1,000 unique session requests the process memory stays under
      a defined ceiling (no unbounded growth)
- [ ] Navigator cache never serves a stale object for a different DB
      session
- [ ] Cleanup endpoint evicts cached state managers
- [ ] Existing tests pass with no behaviour change

## Risks & Rollback

Evicting a cache entry means the next request for that session rebuilds
state from the database, which is slightly slower but correct. Rollback:
revert to plain dicts.
