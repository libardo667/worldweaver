# Batch B Frontend Source Slice 15

Date: `2026-03-06`
Status: `completed`

## Scope
- Continue `frontend_source` simplification by extracting mode payload assembly from `App.tsx` into a dedicated hook.
- Enforce explicit lane-context payload schema boundaries for Explore mode to reduce mixed mode/data wiring drift.

## Changes
1. Added `client/src/hooks/useModeRouterPayload.ts`:
- introduced `useModeRouterPayload(...)` hook that returns `ModeRouterPayload`.
- added typed schema groups for Explore mode:
  - `onboarding`
  - `memory`
  - `lanes.scene`
  - `lanes.player`
  - `lanes.place`
- centralized payload assembly in `buildExplorePayload(...)` to keep mode/lane contract mapping in one place.

2. Refactored `client/src/App.tsx`:
- removed the large inline `useMemo<ModeRouterPayload>(...)` assembly block.
- replaced it with `useModeRouterPayload(...)` and grouped mode context inputs.
- kept runtime behavior unchanged while making payload ownership more explicit.

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict`

Results:
- frontend build: pass
- strict gate: pass (`590 passed`)

## Batch B Impact
- Reduced one of the largest remaining mixed concerns in `App.tsx` by moving mode payload contract assembly to a dedicated hook boundary.
- Added typed lane-context grouping that better matches v3 world/scene/player composition seams.
