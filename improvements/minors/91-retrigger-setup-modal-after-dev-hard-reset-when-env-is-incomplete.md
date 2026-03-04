# Re-trigger setup modal after dev hard reset when env setup is incomplete

## Problem

`/api/dev/hard-reset` can start a fresh world thread, but local operator setup
requirements (API key/model readiness) are not re-evaluated as part of the
post-reset UX. If `.env` is missing one or both required fields, users can
immediately hit runtime failures after reset.

## Proposed Solution

Extend reset flow so setup readiness is checked and enforced every time after
dev hard reset (when dev reset is enabled), but only when env/runtime setup is
incomplete.

1. After successful dev hard reset, client requests setup status before loading
   onboarding or first scene.
2. If setup is incomplete, open the same blocking setup modal from minor `90`.
3. If setup is complete, continue current reset flow unchanged.
4. Preserve existing feature-flag behavior (`WW_ENABLE_DEV_RESET`).

## Files Affected

- `client/src/App.tsx`
- `client/src/api/wwClient.ts`
- `src/api/game/state.py` (only if reset response metadata needs extension)
- `tests/api/test_game_endpoints.py`
- `client` test files for reset/setup flow (if present)

## Acceptance Criteria

- [ ] With `WW_ENABLE_DEV_RESET=true`, dev hard reset re-checks setup readiness.
- [ ] Setup modal appears post-reset only when API key/model is missing.
- [ ] Reset flow remains unchanged when setup is already complete.
- [ ] No API key values are exposed in reset/status responses.
- [ ] `python -m pytest -q` and `npm --prefix client run build` pass.
