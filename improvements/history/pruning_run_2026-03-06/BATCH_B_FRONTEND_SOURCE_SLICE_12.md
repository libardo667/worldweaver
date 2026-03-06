# Batch B Frontend Source Slice 12

Date: `2026-03-06`
Status: `completed`

## Scope
- Continue `frontend_source` simplification by extracting session lifecycle handlers from `App.tsx`.
- Separate world bootstrap flow from thread/world reset flows and make cache invalidation seams explicit.

## Changes
1. Added `client/src/hooks/useSessionLifecycle.ts`:
- extracted:
  - `handleOnboardingSubmit(...)`
  - `handleResetSession(...)`
  - `handleDevHardReset(...)`
- introduced explicit lifecycle seams:
  - `resetTurnRuntimeContext(...)`
  - `invalidateProjectionCaches("thread" | "world")`
- kept existing behavior and toast messaging while centralizing flow logic.

2. Refactored `client/src/App.tsx`:
- removed inline session lifecycle handlers and local storage prefix reset helper.
- wired `useSessionLifecycle(...)` with existing state/update callbacks.
- retained `applyReplacementSessionState(...)` in App as local UI-state reset boundary.

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict`

Results:
- frontend build: pass
- strict gate: pass (`590 passed`)

## Batch B Impact
- Reduced `App.tsx` lifecycle complexity by moving bootstrap/reset orchestration into one dedicated hook.
- Added named cache invalidation boundaries needed for future v3 projection/cache policies.
