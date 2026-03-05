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

## Scope Boundaries

- Keep API route and response contracts unchanged.
- Keep fallback deterministic and local (no new model calls).
- Add behavior in existing turn/state/semantic paths only; no schema migration.

## Assumptions

- Initial-turn progression is represented by story-arc turn count (`_story_arc.turn_count`).
- `central_tension` in world bible is the best deterministic tension signal when available.
- Player role context can be derived from existing state variables (`player_role`, `character_profile`, etc.).

## Files Affected

- `src/services/state_manager.py`
- `src/services/turn_service.py`
- `tests/service/test_state_manager.py`
- `tests/service/test_semantic_selector.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [x] Sessions do not continue past initial gameplay turns with empty
      `primary_goal`.
- [x] Fallback goal generation is deterministic and idempotent per session.
- [x] Goal context appears in semantic scoring inputs after fallback assignment.

## Validation Commands

- `python -m pytest tests/service/test_state_manager.py -q`
- `python -m pytest tests/service/test_semantic_selector.py -q`
- `python -m pytest tests/api/test_game_endpoints.py -q`
- `python scripts/dev.py lint-all`
- `python -m pytest -q`
- `npm --prefix client run build`

## Rollback Notes

- Revert this item's state-manager backfill + turn orchestration wiring + tests.
- No migrations or irreversible data changes were introduced.
