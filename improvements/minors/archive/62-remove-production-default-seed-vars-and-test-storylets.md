# Remove production default seed vars and test storylets

## Problem
Legacy seed data still defines gameplay defaults that leak into normal sessions:
- `has_pickaxe=True` is part of `DEFAULT_SESSION_VARS` (`src/services/seed_data.py:10-13`).
- `seed_if_empty` inserts "Test *" directional storylets (`src/services/seed_data.py:38-49`).
- `session_service` applies those defaults to every new state manager (`src/services/session_service.py:101-102`).

This undermines onboarding intent and world-specific opening quality.

## Proposed Solution
1. Split seed concerns:
   - production baseline vars (neutral, no narrative assumptions),
   - explicit test fixture seeds (legacy directional stubs).
2. Remove narrative-bearing defaults (including `has_pickaxe`) from production session defaults.
3. Gate legacy storylet seed insertion behind explicit dev/test configuration so startup/reset paths do not silently inject test content.

## Files Affected
- `src/services/seed_data.py`
- `src/services/session_service.py`
- `src/config.py`
- `main.py`
- `tests/conftest.py`
- `tests/services/test_session_service.py`

## Acceptance Criteria
- [x] Production session defaults no longer include `has_pickaxe`.
- [x] Legacy "Test *" storylets are not inserted unless explicit dev/test flag is enabled.
- [x] Existing tests that rely on legacy seeds use explicit fixture/flag setup.
- [x] `python -m pytest -q` passes with updated defaults.
