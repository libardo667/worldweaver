# Harden session cache thread safety and worker strategy for coherent runtime behavior

## Problem

`src/services/session_service.py` uses process-local caches
(`_state_managers`, `_spatial_navigators`) for active sessions. This is fast in
single-process dev mode, but behavior can diverge under concurrency or multiple
workers without an explicit consistency strategy.

## Proposed Solution

Define and implement a clear session consistency strategy:

1. Add per-session synchronization around load/mutate/save paths to prevent
   intra-process race conditions.
2. Introduce explicit runtime modes:
   - single-process cache mode (dev/default),
   - stateless-per-request reconstruction mode, and/or
   - shared-cache mode (optional external store).
3. Ensure mode selection is config-driven and documented.
4. Add deterministic concurrency tests for concurrent `/api/next` + `/api/action`
   requests against the same session.
5. Update operational docs with worker-count guidance and expected guarantees.

## Files Affected

- `src/services/session_service.py`
- `src/services/cache.py`
- `src/config.py`
- `src/api/game/action.py`
- `src/api/game/story.py`
- `tests/service/test_session_service.py`
- `tests/integration/test_concurrent_session_requests.py`
- `README.md`
- `CLAUDE.md`

## Acceptance Criteria

- [ ] Concurrent requests for the same session do not produce torn writes or
      out-of-order state persistence.
- [ ] Session consistency mode is explicit and configurable.
- [ ] Multi-worker behavior and caveats are documented in runtime docs.
- [ ] Cache invalidation and cleanup behavior is covered by tests.
- [ ] `python -m pytest -q tests/service/test_session_service.py
      tests/integration/test_concurrent_session_requests.py` passes.

## Risks & Rollback

Risk: added synchronization can increase latency or reduce throughput.

Rollback:

1. Keep synchronization/mode changes behind config toggles.
2. Revert to current cache behavior for local dev if throughput regresses
   materially.
3. Preserve tests to prevent silent reintroduction of race-prone paths.

