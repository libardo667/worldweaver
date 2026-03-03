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

## Acceptance Criteria
- [ ] With Constellation enabled, the view renders a visible node-link graph when storylet data is present.
- [ ] Node selection in the graph and list stay in sync and update the existing detail panel.
- [ ] Graph includes controls to toggle semantic and spatial edges without reloading the page.
- [ ] Existing Constellation API usage and payload contracts remain unchanged.
- [ ] Existing list/detail fallback still works when graph rendering is unavailable or data is sparse.
- [ ] `npm --prefix client run build` succeeds.
