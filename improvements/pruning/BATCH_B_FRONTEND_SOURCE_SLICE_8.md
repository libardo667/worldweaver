# Batch B Frontend Source Slice 8

Date: `2026-03-06`
Status: `completed`

## Scope
- Continue `frontend_source` simplification by making turn orchestration lane-aware at the narrator seam.
- Remove inline lane-neutral notice strings from orchestration logic and route notice/outcome handling through lane adapters.

## Changes
1. Refactored `client/src/app/v3NarratorStubs.ts`:
- introduced `V3NarratorLaneAdapter` and `V3NarratorHooks.lanes` (`world`, `scene`, `player`).
- added shared helpers:
  - `getSceneLaneDefaultNotice(...)`
  - `getNarratorLaneAdapter(...)`
- expanded turn result shape to include lane metadata for adapter callbacks.

2. Refactored `client/src/hooks/useTurnOrchestration.ts`:
- replaced per-handler hardcoded notices with `resolveSceneLaneNotice(...)` using scene lane defaults and adapter overrides.
- centralized lane callback emission with `emitLaneTurnResult(...)` across `scene/world/player`.
- retained choice/action/move runtime behavior and error handling.

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict`

Results:
- frontend build: pass
- strict gate: pass (`590 passed`)

## Batch B Impact
- Established explicit world/scene/player callback boundaries inside turn orchestration.
- Reduced notice-string drift risk by moving default scene notices into v3 narrator seam helpers.
