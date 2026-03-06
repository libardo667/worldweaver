# Batch B Frontend Source Slice 4

Date: `2026-03-06`
Status: `completed`

## Scope
- Extract the Explore-mode routing branch from `App.tsx` into a dedicated component.
- Keep `App.tsx` focused on high-level mode switching and shared orchestration handlers.

## Changes
1. Added `client/src/components/ExploreMode.tsx`:
- owns Explore routing (`needsOnboarding` -> `SetupOnboarding`, else `AppShell` path).
- composes `MemoryPanel`, `ExploreCenterColumn`, and `PlacePanel` behind a single prop boundary.

2. Refactored `client/src/App.tsx`:
- replaced large inline Explore-mode routing conditional with `<ExploreMode ... />`.
- removed direct Explore-branch component imports now encapsulated by `ExploreMode`.

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict`

Results:
- frontend build: pass
- strict gate: pass (`590 passed`)

## Batch B Impact
- `App.tsx` reduced from `924` lines to `903` lines in this slice.
- Explore path now has a dedicated boundary, enabling future simplification of prop surfaces and handler grouping.
