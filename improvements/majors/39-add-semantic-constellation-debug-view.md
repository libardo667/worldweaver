# Add an optional semantic constellation debug view

## Problem
WorldWeaver’s core differentiator is movement through meaning-space, but the player (and developer) currently cannot see it. Debugging semantic selection and tuning diversity is difficult without:
- visibility into “nearby” narrative possibilities,
- a way to inspect similarity scores and candidate sets,
- a visualization surface for constellations of storylets.

## Proposed Solution
Add an optional semantic constellation view that is safe by default and useful for debugging and “wow” moments.

This major includes one additive backend endpoint plus a client view.

Backend (additive, non-breaking):
1. Add a new router `src/api/semantic.py` mounted under `/api/semantic`.
2. Implement `GET /api/semantic/constellation/{session_id}` returning:
   - current context summary (location, a few vars),
   - top-N scored storylets with fields: id, title, position (if any), score,
   - optional lightweight edges:
     - spatial adjacency (N/NE/E… neighbors),
     - top-K semantic neighbors (id list only).
3. Compute scores by reusing existing semantic selector machinery:
   - build context vector from current state + world memory,
   - score storylets with embeddings,
   - apply floor probability and recency penalties.
4. Gate the endpoint behind an environment variable (default off):
   - `WW_ENABLE_CONSTELLATION=1`.

Client:
1. Add a Constellation view that renders:
   - a list or simple graph (v1) of the scored storylets,
   - filters (top-N, show only accessible, show only in radius).
2. Clicking a storylet can:
   - open details,
   - optionally “jump” by setting location vars (debug-only).

Recommended backend files:
- `src/api/semantic.py` (new)
- `src/services/constellation_service.py` (new)
- `src/config.py` (add `enable_constellation` flag)

Recommended client files:
- `client/src/views/ConstellationView.tsx` (new)

## Files Affected
- src/api/semantic.py (new)
- src/services/constellation_service.py (new)
- src/config.py (modify: feature flag)
- main.py (modify: include router)
- tests/api/test_semantic_constellation_endpoint.py (new)
- client/src/views/ConstellationView.tsx (new)
- client/src/App.tsx (modify: add nav to constellation when enabled)

## Acceptance Criteria
- [ ] When `WW_ENABLE_CONSTELLATION=1`, `GET /api/semantic/constellation/{session_id}` returns top-N scored storylets with deterministic keys and no embeddings leaked.
- [ ] When the flag is off, the endpoint returns 404 or a clear disabled response.
- [ ] The endpoint uses existing semantic selection rules (floor probability, recency penalty).
- [ ] Client can render constellation results in a dedicated view and allow basic filtering.
- [ ] New tests pass and existing backend tests remain green (`pytest -q`).

## Risks & Rollback
Primary risks:
- Leaking too much internal data (raw embeddings, sensitive prompts). Mitigate by returning only scores and metadata.
- Performance cost if scoring scans all storylets each request. Mitigate with caching and max-N limits.
- Feature flag drift (ensure default-off).

Rollback:
- Disable via env flag, then remove the router include and delete the new service module if necessary.
