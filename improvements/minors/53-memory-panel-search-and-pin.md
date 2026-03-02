# Add memory panel search and pinning UX

## Problem
World memory exists, but players need a low-friction way to query and pin facts. Without this, memory remains hidden and the world feels less “alive.”

## Proposed Solution
In the Memory panel:
- Add a search input that calls `/api/world/facts?query=...`.
- Display results as cards and allow pinning.
- Pinned facts appear in both Explore and Reflect modes.

Pins can be stored locally first; optionally mirror to session vars later.

## Files Affected
- client/src/components/MemoryPanel.tsx
- client/src/components/FactsSearch.tsx (new)
- client/src/state/pinsStore.ts (new)

## Acceptance Criteria
- Searching returns and renders results from `/api/world/facts`.
- Player can pin/unpin a fact and see pins persist across navigation in the session.
- No backend changes required.
