# Add continuous loading via frontier prefetch and cached storylet stubs

## Problem
WorldWeaver's turn latency can be 20–30 seconds when a turn requires one or more expensive LLM calls (especially freeform actions, runtime synthesis, and embedding work). This produces a jarring experience where the player clicks a choice and then waits with no sense of momentum.

The system needs a "fast lane / slow lane" architecture:
- fast lane: always able to produce a coherent next step quickly,
- slow lane: continuously expands the nearby world in the background so the fast lane has ready-to-use options.

## Proposed Solution
Introduce a **Frontier Prefetch** pipeline that runs in the background and keeps a small cache of "nearby" narrative content (semantic and geographic) per session.

1. Create a server-side Prefetch service
   - Maintain a per-session cache of prefetched artifacts:
     - storylet stubs (title, requires, choices, short premise),
     - optional positional hints (x/y) and "directional leads",
     - context summary used to generate them (for debugging).
   - Store the cache in-memory with TTL (v1). Optionally persist to DB later.

2. Trigger background prefetch after player-visible steps
   - After `/api/next` responds, schedule a background job to:
     - ensure >= N eligible storylets exist within the current neighborhood,
     - ensure >= M semantically relevant leads exist for the current context,
     - generate a small number of runtime-synthesized candidates if sparse.
   - After `/api/action` completes, schedule the same, using the updated state and newly recorded world facts.

3. Generate structure, not full prose
   - Prefetch generates **stubs** and embeddings (when possible), not long-form narration.
   - Narration remains a fast-lane step that merges a chosen stub with the player's action/choice.

4. Prefer prefetched candidates in selection flow
   - When selecting a next storylet, prefer an eligible prefetched stub for:
     - the current location,
     - or the player's semantic goal/lens direction,
     - subject to requirement checks and recency penalties.

5. Budgets and safety rails
   - Hard caps per session and per time window (already present for runtime synthesis; extend to prefetch).
   - Feature flags:
     - `enable_frontier_prefetch`
     - `prefetch_max_per_session`
     - `prefetch_ttl_seconds`
     - `prefetch_idle_trigger_seconds` (client may use this later)
   - Prefetch failures are silent and never block player-visible requests.

## Files Affected
- `src/services/prefetch_service.py` (new)
- `src/services/storylet_selector.py` (prefer prefetched stubs when available)
- `src/api/game/story.py` (schedule prefetch after `/api/next`)
- `src/api/game/action.py` (schedule prefetch after `/api/action` and `/api/action/stream`)
- `src/config.py` (new flags + budgets)
- `tests/service/test_prefetch_service.py` (new)
- `tests/api/test_game_endpoints.py` (extend: prefetch scheduling does not break responses)

## Acceptance Criteria
- [ ] A background prefetch job can be scheduled after `/api/next` and `/api/action` without blocking the response.
- [ ] Prefetched artifacts are cached per-session with a TTL and capped size.
- [ ] Selection can use prefetched storylet stubs when eligible, falling back safely when none exist.
- [ ] Prefetch never changes session state directly and never mutates world facts; it only expands candidate options.
- [ ] Prefetch respects strict budgets and can be disabled via a feature flag.
- [ ] `pytest -q` passes.

## Risks & Rollback
Prefetch can increase API cost and complexity and can introduce subtle consistency bugs if it mutates state. Mitigate by treating prefetch as read-only + additive candidate generation. Roll back by disabling the feature flag and removing the selection preference logic; the core experience should remain functional.
