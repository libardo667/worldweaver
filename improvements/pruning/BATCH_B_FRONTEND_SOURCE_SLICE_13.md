# Batch B Frontend Source Slice 13

Date: `2026-03-06`
Status: `completed`

## Scope
- Continue `frontend_source` simplification by extracting App mode-switch rendering into a typed router boundary.
- Reduce broad per-branch prop fan-out in `App.tsx` by passing grouped mode payload bundles.

## Changes
1. Added `client/src/components/ModeRouter.tsx`:
- introduced typed `ModeRouterPayload` contract:
  - `explore`
  - `reflect`
  - `create`
  - `constellation`
- centralizes mode-to-view routing in one component.

2. Refactored mode/view prop contracts to export reusable types:
- `client/src/components/ExploreMode.tsx` -> `ExploreModeProps`
- `client/src/views/ReflectView.tsx` -> `ReflectViewProps`
- `client/src/views/CreateView.tsx` -> `CreateViewProps`
- `client/src/views/ConstellationView.tsx` -> `ConstellationViewProps`

3. Refactored `client/src/App.tsx`:
- replaced inline mode conditional render chain with:
  - `modeRouterPayload` (`useMemo`) typed by `ModeRouterPayload`
  - `<ModeRouter mode={mode} payload={modeRouterPayload} />`
- retained existing runtime behavior and per-mode view wiring.

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict`

Results:
- frontend build: pass
- strict gate: pass (`590 passed`)

## Batch B Impact
- Removed the remaining large mode-branch render block from `App.tsx`.
- Established a typed, explicit mode routing boundary aligned with v3 lane/context composition work.
