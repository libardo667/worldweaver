# Demote compass/spatial movement to an optional assistive layer

## Problem

Compass movement is currently coupled tightly enough to player turn flow that reliability issues in spatial data and traversability can degrade perceived turn quality. Spatial affordances are sometimes inconsistent with actual movement outcomes, and spatial refresh is treated as part of normal post-turn UI work.

At the same time, core narrative progression (`/api/next`, freeform actions, semantic selection, world memory) does not require compass movement to function. This mismatch makes a non-core assistive feature feel like a core dependency.

## Proposed Solution

Refactor navigation layering so compass/spatial behavior is optional, non-blocking, and explicitly secondary to core narrative flow.

1. Introduce explicit feature controls for assistive spatial UI:
   - disable compass surface without disabling story progression
   - keep spatial endpoints available for debug/advanced use
2. Decouple spatial refresh and compass state updates from turn-critical completion paths.
3. Preserve location-based narrative continuity and semantic selection regardless of compass state.
4. Tighten spatial API/client contracts so accessibility and traversability are represented consistently.
5. Prevent automatic “spatial fixer” operations from mutating content in normal runtime paths unless explicitly enabled.
6. Keep route/payload compatibility unless explicitly approved, consistent with roadmap guardrails.

## Files Affected

- `src/config.py` (feature controls)
- `src/api/game/spatial.py` (contract/shape alignment where required)
- `src/models/schemas.py` (if spatial response model extensions are required)
- `src/services/story_smoother.py` (spatial-fix behavior gating)
- `src/services/auto_improvement.py` (spatial-fix invocation policy)
- `client/src/App.tsx` (non-blocking spatial refresh strategy)
- `client/src/components/Compass.tsx`
- `client/src/hooks/useKeyboardNavigation.ts`
- `client/src/types.ts`
- `tests/api/*spatial*`
- `tests/integration/*spatial*`

## Acceptance Criteria

- [ ] Story progression remains fully playable with compass UI disabled.
- [ ] Post-choice and post-action rendering no longer depends on successful spatial refresh.
- [ ] Compass affordances (when enabled) align with traversability semantics.
- [ ] Spatial auto-fix mutations are disabled by default in normal runtime paths.
- [ ] Freeform action, semantic selection, and world-memory behavior remain unchanged in baseline flows.
- [ ] `python -m pytest -q` and `npm --prefix client run build` pass.

## Risks & Rollback

Making compass optional can reduce discoverability of physical navigation and may hide useful spatial affordances for some play styles. Roll back by re-enabling compass defaults and restoring previous post-turn refresh coupling behind feature flags while preserving contract-compatible API behavior.

