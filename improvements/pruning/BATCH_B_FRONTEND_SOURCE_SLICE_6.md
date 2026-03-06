# Batch B Frontend Source Slice 6

Date: `2026-03-06`
Status: `completed`

## Scope
- Continue `frontend_source` simplification by reducing repeated turn-lifecycle state wiring.
- Keep behavior unchanged while centralizing shared begin/end turn operation updates.

## Changes
1. Refactored `client/src/App.tsx`:
- added `beginTurnOperation(...)` helper for shared start-of-turn state updates.
- added `finishTurnOperation(...)` helper for shared end-of-turn state cleanup.
- applied helpers across bootstrap/choice/action/move/reset/dev-reset/constellation/onboarding flows.

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict`

Results:
- frontend build: pass
- strict gate: pass (`590 passed`)

## Batch B Impact
- Reduced repeated phase/notice/draft reset boilerplate in multiple async handlers.
- Lowered drift risk between turn lifecycle paths while preserving existing behavior.
