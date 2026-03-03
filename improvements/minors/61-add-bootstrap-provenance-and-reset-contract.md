# Add bootstrap provenance and reset contract

## Problem
`POST /api/reset-session` currently deletes data and immediately reseeds legacy storylets (`src/api/game/state.py:226-238`), but the response does not define whether onboarding is required next. There is no persisted marker indicating whether a session has completed world bootstrap, making critical-path behavior implicit and fragile.

## Proposed Solution
1. Define reset semantics explicitly in API response:
   - include fields like `requires_onboarding`, `world_bootstrap_state`, and `legacy_seed_mode`.
2. Add bootstrap provenance fields in session state (for example: `bootstrap_state`, `bootstrap_source`, `bootstrap_completed_at`).
3. Keep legacy reseed behavior only behind an explicit flag (for test/dev compatibility), and expose that mode in the response for debug clarity.

## Files Affected
- `src/api/game/state.py`
- `src/models/schemas.py`
- `src/services/session_service.py`
- `src/config.py`
- `tests/api/test_state_endpoints.py`

## Acceptance Criteria
- [ ] Reset response includes explicit onboarding/bootstrap status fields.
- [ ] Session state records bootstrap provenance after bootstrap completion.
- [ ] Legacy reseed mode is disabled by default and can be enabled explicitly for tests/dev.
- [ ] API tests cover both default reset behavior and legacy reseed compatibility mode.
