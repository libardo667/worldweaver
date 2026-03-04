# Add a node-link graph renderer for Constellation mode

## Problem
Constellation mode currently renders as a scored list plus detail panel (`client/src/views/ConstellationView.tsx`). That satisfies the archived v1 scope, but it does not deliver the visual "constellation" graph users expect. This makes it harder to quickly inspect clusters, outliers, and edge structure while debugging semantic selection.

## Proposed Solution
Add a client-side node-link graph panel to Constellation mode, reusing the existing payload shape from `GET /api/semantic/constellation/{session_id}` and keeping backend contracts unchanged.

1. Extend `ConstellationView` with an SVG (or canvas) graph layer that renders:
   - nodes for returned storylets,
   - semantic neighbor edges,
   - optional spatial adjacency edges.
2. Map visual channels to current metadata:
   - node size or intensity by `score`,
   - blocked vs accessible style by `accessible`,
   - selected node highlight.
3. Keep existing list/detail UI as fallback and secondary inspector.
4. Add graph controls:
   - show/hide semantic edges,
   - show/hide spatial edges,
   - reset layout.
5. Keep click behavior consistent:
   - clicking a node selects it and updates detail pane,
   - existing "Jump to location" action remains unchanged.
6. Preserve feature-flag behavior (`VITE_WW_ENABLE_CONSTELLATION`) and avoid API changes.

## Files Affected
- client/src/views/ConstellationView.tsx
- client/src/styles.css
- client/src/types.ts (only if view-model helper types are needed)
- client/src/App.tsx (only if mode wiring changes are required)

## Scope Boundaries
- Frontend-only change; no backend route, payload, or schema edits.
- Keep existing Constellation list/detail behavior as a working fallback.
- Do not change mode gating behavior (`VITE_WW_ENABLE_CONSTELLATION`).

## Assumptions
- Constellation payload continues to include `storylets[].edges.semantic_neighbors` and
  `storylets[].edges.spatial_neighbors`.
- Graph rendering can be deterministic and client-only (no persisted layout state).
- Sparse data (single node or no edges) must still render a usable inspector flow.

## Validation Commands
- `npm --prefix client run build`
- `python -m pytest -q`

## Rollback Notes
- Revert this item's frontend commit(s) to return to list/detail-only rendering.
- No migrations or persisted state changes are introduced.
- Emergency disable remains `VITE_WW_ENABLE_CONSTELLATION=false` to remove Constellation mode.

## Acceptance Criteria
- [x] With Constellation enabled, the view renders a visible node-link graph when storylet data is present.
- [x] Node selection in the graph and list stay in sync and update the existing detail panel.
- [x] Graph includes controls to toggle semantic and spatial edges without reloading the page.
- [x] Existing Constellation API usage and payload contracts remain unchanged.
- [x] Existing list/detail fallback still works when graph rendering is unavailable or data is sparse.
- [x] `npm --prefix client run build` succeeds.

## Execution Evidence (March 3, 2026)
- Changed:
  - `client/src/views/ConstellationView.tsx` (added SVG graph rendering, edge toggles, layout reset, selection sync)
  - `client/src/styles.css` (added graph panel layout/styles and responsive grid update)
- Why:
  - Deliver a visual constellation graph while preserving existing list/detail inspector as fallback.
- Verified:
  - `npm --prefix client run build` passed.
  - By implementation inspection: no API request/response contract changes; existing Constellation endpoint usage unchanged.
  - Graph/list both drive `selectedId`, so detail panel remains single source of truth.
- Remaining risk:
  - No dedicated frontend interaction tests currently validate graph UI behavior.
  - `python -m pytest -q` currently fails on unrelated baseline tests:
    - `tests/api/test_game_endpoints.py::TestGameEndpoints::test_cleanup_removes_stale_sessions`
    - `tests/diagnostic/test_llm_config.py::test_default_settings`

## Item Status
- `verify` (feature implemented; global backend test baseline currently red for unrelated failures)
