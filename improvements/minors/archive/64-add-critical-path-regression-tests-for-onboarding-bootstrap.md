# Add critical-path regression tests for onboarding bootstrap

## Problem
There is no focused regression suite covering `reset -> onboarding bootstrap -> first /api/next`, so legacy seed coupling and onboarding drift can reappear unnoticed. Current tests do not enforce that onboarding inputs influence first-turn context or that default session vars stay neutral.

## Proposed Solution
1. Add API-level tests for reset/bootstrap/next sequencing:
   - reset leaves onboarding-required state,
   - bootstrap marks session provenance,
   - first `/api/next` after bootstrap uses bootstrap-generated pool.
2. Add service-level tests that default session vars do not inject narrative-specific items (for example `has_pickaxe`).
3. Add assertions that onboarding fields (`world_theme`, `player_role`) are present in generation context for opening storylet creation.

## Files Affected
- `tests/api/test_game_endpoints.py`
- `tests/api/test_state_endpoints.py`
- `tests/services/test_session_service.py`
- `tests/services/test_storylet_selector.py`

## Acceptance Criteria
- [x] Regression tests cover reset/bootstrap/next ordering with deterministic assertions.
- [x] Tests fail if `has_pickaxe` is reintroduced as an implicit default.
- [x] Tests fail if onboarding theme/role are dropped from bootstrap context.
- [x] `python -m pytest -q` passes with the new coverage.
