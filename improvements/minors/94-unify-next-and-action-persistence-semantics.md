# Minor 94: Unify `/next` and `/action` persistence semantics for core world context

## Problem Statement
During a 30-turn playback analysis, it was discovered that while the `/api/next` endpoint correctly preserves sticky session assets like `_world_bible` and advances the `_story_arc`, calls to the `/api/action` (freeform insertion) endpoint drop the `_world_bible` from the state entirely and maliciously reset the `_story_arc` to `setup_act` / turn 1. This causes the LLM to lose spatial anchor context precisely when it needs it most (during freeform interaction) and ruins arc pacing.

## Proposed Solution
Unify the shared session persistence logic across both API endpoints.

### Acceptance Criteria
- [ ] Investigate `/api/action` and ensure the internal dispatch or `state.apply_world_delta` doesn't overwrite sticky configuration dicts with null or empty arrays.
- [ ] Determine why `world_memory.record_event` or the storylet selection logic during `action` paths resets the story arc. Ensure the arc context respects chronological continuation.
- [ ] Ensure that `_world_bible` remains present in the global state dump for all turns 1-100 regardless of action mixing.

## Expected Files Changed
- `src/api/game/action.py`
- `src/services/session_service.py` or `src/services/state_manager.py`

## Rollback Plan
- Revert the arc increment mapping and contextual saves.
