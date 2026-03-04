# Backfill a primary goal thesis when empty after the initial turn

## Problem

Goal/arc systems exist, but sessions can still proceed with empty primary goal
state, weakening semantic context and arc coherence.

## Proposed Solution

Add deterministic goal fallback behavior:

1. If `primary_goal` is empty after turn 1, derive a short fallback thesis from
   world bible tension + player role context.
2. Persist fallback as explicit goal state update with source metadata.
3. Ensure fallback runs once unless user/system later sets an explicit goal.

## Files Affected

- `src/services/state_manager.py`
- `src/api/game/story.py`
- `src/services/semantic_selector.py`
- `tests/service/test_state_manager.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [ ] Sessions do not continue past initial gameplay turns with empty
      `primary_goal`.
- [ ] Fallback goal generation is deterministic and idempotent per session.
- [ ] Goal context appears in semantic scoring inputs after fallback assignment.

