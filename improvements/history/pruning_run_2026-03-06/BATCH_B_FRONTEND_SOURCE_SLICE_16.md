# Batch B Frontend Source Slice 16

Date: `2026-03-06`
Status: `completed`

## Scope
- Complete `frontend_source` simplification for Batch B by introducing explicit mode-level lane-context payload contracts.
- Decouple mode payload routing from view-internal flat prop wiring through a shared normalization seam.

## Changes
1. Added shared payload contract module:
- `client/src/components/exploreModePayload.ts`
- introduced:
  - `ExploreModePayload`
  - explicit lane contracts (`scene`, `player`, `place`)
  - onboarding/memory contract groups
  - `normalizeExploreModePayload(...)` for mode-level shape normalization.

2. Refactored `client/src/components/ExploreMode.tsx`:
- replaced flat prop list with single `payload: ExploreModePayload`.
- now consumes grouped `onboarding`, `memory`, and `lanes` contexts directly.

3. Refactored `client/src/components/ModeRouter.tsx`:
- changed `ModeRouterPayload["explore"]` from `ExploreModeProps` (view-internal shape) to `ExploreModePayload` (shared contract shape).
- routes Explore via `<ExploreMode payload={payload.explore} />`.

4. Refactored `client/src/hooks/useModeRouterPayload.ts`:
- simplified to accept `explore: ExploreModePayload`.
- centralized contract normalization by calling `normalizeExploreModePayload(...)` before payload handoff.

5. Updated `client/src/App.tsx` Explore payload assembly:
- moved onboarding notice field to contract name `pendingNotice`.
- made scene-lane `backendNotice` explicit in lane contract input.

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict`

Results:
- frontend build: pass
- strict gate: pass (`590 passed`)

## Batch B Impact
- Mode-level payload contracts are now explicit and normalized before routing, reducing drift between `App.tsx` assembly and Explore view internals.
- Frontend Batch B simplification is now closed at slice 16 with stable quality gates.
