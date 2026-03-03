# Redact compass directions that are not actually traversable

## Problem
The compass currently enables movement affordances from `directions` presence alone, but movement can still fail with `403 Cannot move in that direction` when target requirements are not met. This creates noisy failed requests and makes compass movement feel unreliable compared to freeform play.

## Proposed Solution
Keep API behavior stable and make the compass reflect true traversability.

1. Use accessibility-aware navigation metadata (reachable vs blocked), not just adjacency.
2. Redact blocked directions from primary compass actions (or render them as clearly non-actionable with an explicit blocked reason).
3. Preserve keyboard navigation behavior with the same accessibility rules.
4. Surface one concise UX message for blocked movement attempts (no repeated noisy toasts).
5. Keep semantic leads/freeform action unchanged; compass remains optional assistive navigation.

## Scope Boundaries
- Keep movement endpoint behavior and status codes unchanged.
- Keep freeform action loop and semantic move intent behavior unchanged.
- Limit UI work to compass/place affordances and movement feedback only.

## Assumptions
- Server-side navigation already computes accessibility per direction.
- Adding optional response metadata is contract-safe for existing clients.
- Compass and keyboard movement should use the same traversability source.

## Files Affected
- `client/src/App.tsx`
- `client/src/components/Compass.tsx`
- `client/src/types.ts` (if richer navigation typing is needed)
- `src/api/game/spatial.py` (only if response needs to expose accessible flags already computed server-side)
- `src/models/schemas.py` (only if spatial response schema needs extension)

## Acceptance Criteria
- [x] Compass buttons are actionable only for directions that are currently traversable.
- [x] Repeated `POST /api/spatial/move/{session_id}` `403` responses caused by clickable blocked directions are eliminated in normal compass use.
- [x] Keyboard compass navigation follows the same traversability rules as pointer interactions.
- [x] Blocked direction state (if shown) is visually distinct and does not appear as a normal move action.
- [x] Existing freeform action loop remains unchanged.
- [x] `python -m pytest -q` passes.
- [x] `npm --prefix client run build` passes.

## Validation Commands
- `python -m pytest -q`
- `npm --prefix client run build`

## Rollback Plan
- Revert the branch commit(s) that introduce `available_directions` wiring and compass gating.
- No feature flag is added; operational rollback is commit revert.
- No irreversible data or migration changes are introduced.

## Closure Evidence (2026-03-03)
- Verified behavior in `client/src/App.tsx`, `client/src/components/Compass.tsx`, and `client/src/hooks/useKeyboardNavigation.ts` aligns compass and keyboard movement with traversability metadata.
- `python -m pytest -q` passed (`476 passed, 12 warnings`).
- `npm --prefix client run build` passed (`tsc --noEmit` + `vite build`).
- Residual risk: existing non-blocking warnings remain in test output (pydantic namespace + SQLAlchemy/sqlite deprecation + one SAWarning) and are tracked outside this item.
