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

## Files Affected
- `client/src/App.tsx`
- `client/src/components/Compass.tsx`
- `client/src/types.ts` (if richer navigation typing is needed)
- `src/api/game/spatial.py` (only if response needs to expose accessible flags already computed server-side)
- `src/models/schemas.py` (only if spatial response schema needs extension)

## Acceptance Criteria
- [ ] Compass buttons are actionable only for directions that are currently traversable.
- [ ] Repeated `POST /api/spatial/move/{session_id}` `403` responses caused by clickable blocked directions are eliminated in normal compass use.
- [ ] Keyboard compass navigation follows the same traversability rules as pointer interactions.
- [ ] Blocked direction state (if shown) is visually distinct and does not appear as a normal move action.
- [ ] Existing freeform action loop remains unchanged.
- [ ] `python -m pytest -q` passes.
- [ ] `npm --prefix client run build` passes.
