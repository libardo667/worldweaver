# Move enhanced storylet selection logic out of the game router

## Problem

`src/api/game.py` currently contains `pick_storylet_enhanced(...)`, which is core business logic (eligibility filtering, semantic scoring, fallback selection). This violates the goal of thin routers and makes selection behavior harder to test and reuse.

## Proposed Solution

1. Create `src/services/storylet_selector.py` and move `pick_storylet_enhanced(...)` there.
2. Keep behavior identical:
   - condition evaluation through `AdvancedStateManager`,
   - semantic selection when embeddings are available,
   - recency-aware scoring,
   - weighted random fallback.
3. Update `src/api/game.py` to call `storylet_selector.pick_storylet_enhanced(...)`.
4. Add/adjust tests in service scope to assert same selection behavior and fallback paths.

## Files Affected

- `src/services/storylet_selector.py` (new)
- `src/api/game.py`
- `tests/service/test_storylet_selector.py` (new)
- `tests/service/test_semantic_selector.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [ ] Storylet selection behavior is unchanged for semantic and non-semantic paths.
- [ ] `src/api/game.py` no longer owns selection internals.
- [ ] Selection logic is directly unit-testable through service tests.
- [ ] `pytest -q` passes.

## Risks & Rollback

Risk is accidental behavior drift during code movement. Roll back by restoring original router function and deleting `storylet_selector.py`.
