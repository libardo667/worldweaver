# PR Evidence

## Change Summary

- Item ID(s): `67-add-dev-runtime-preflight-and-command-surface`
- PR Scope: Added a single-file developer command surface (`scripts/dev.py`) with preflight and common runtime/test/build wrappers, then updated root/client/harness docs to use those commands without changing API behavior.
- Risk Level: `low`

## Behavior Impact

- User-visible changes:
  - New preflight command with explicit pass/fail remediation messaging.
  - New canonical wrapper commands for backend/client/test/build/verify.
  - Updated runtime docs to use a consistent command surface.
- Non-user-visible changes:
  - `.env.example` now clarifies API-key requirement and optional client override file.
- Explicit non-goals:
  - No route/path/payload changes.
  - No runtime orchestration via compose/tasks (still tracked by major `46`).

## Validation Results

- `python scripts/dev.py preflight` -> `pass` (all required checks passed)
- `python scripts/dev.py test` -> `pass` (`469 passed, 11 warnings`)
- `python scripts/dev.py build` -> `pass` (`vite build completed successfully`)
- `python scripts/dev.py verify` -> `pass` (tests + build succeeded)

## Contract and Compatibility

- Contract/API changes: `none`
- Migration/state changes: `none`
- Backward compatibility: Existing direct commands (`uvicorn`, `npm --prefix client run dev`, `python -m pytest -q`) remain valid.

## Metrics (if applicable)

- Baseline:
  - N/A (docs + script command surface)
- After:
  - N/A (docs + script command surface)

## Risks

- Wrapper script can drift from runtime behavior if underlying commands change and docs are not updated.
- Preflight enforces API-key presence for live runtime, which may require explicit setup in new environments.

## Rollback Plan

- Fast disable path: Use existing direct commands and ignore `scripts/dev.py`.
- Full revert path: Revert commit containing `scripts/dev.py` and related doc updates.

## Follow-up Work

- `46-operationalize-dev-runtime-with-compose-and-tasks.md`
- `68-make-place-panel-refresh-best-effort-after-turn-render.md`
