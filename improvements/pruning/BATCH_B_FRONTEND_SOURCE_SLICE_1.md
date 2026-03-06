# Batch B Frontend Source Slice 1

Date: `2026-03-06`
Status: `completed`

## Scope
- Start `frontend_source` simplification by reducing `App.tsx` monolith size without changing behavior.
- Isolate reusable frontend runtime/config helpers into a dedicated module.

## Changes
1. Added `client/src/app/appHelpers.ts`:
- centralizes frontend constants and environment flags used by app runtime flow.
- centralizes var/payload transformation helpers (`normalizeVars`, `toNextPayloadVars`, `mergePreferenceVars`, etc.).
- centralizes prompt and movement/error helpers used across action/move/onboarding flows.

2. Refactored `client/src/App.tsx`:
- removed large inline helper/constant block.
- now imports helper symbols from `./app/appHelpers`.
- keeps component logic focused on state/effects/handlers/rendering.

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict`

Results:
- frontend build: pass
- strict gate: pass (`590 passed`)

## Batch B Impact
- Reduced `App.tsx` complexity and improved separation-of-concerns.
- Created reusable boundary for future frontend simplify slices (extracting additional App handlers/views safely).
