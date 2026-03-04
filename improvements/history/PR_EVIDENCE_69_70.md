# PR Evidence

## Change Summary

- Item ID(s): `69-add-root-runtime-readme-and-harness-link`, `70-remove-stale-run-true-tests-command-references`
- PR Scope: Added a root runtime README and aligned active documentation with the actual runnable command surface by removing stale `run_true_tests.py` references. Updated harness bootstrap status and roadmap progress for these two blocker minors only.
- Risk Level: `low`

## Behavior Impact

- User-visible changes:
  - New root `README.md` with canonical setup/run/test/build commands.
  - Updated docs no longer direct users to a missing test runner script.
- Non-user-visible changes:
  - Harness checklist install linkage gap resolved.
  - Minor acceptance checklists and roadmap status updated.
- Explicit non-goals:
  - No API, runtime, or application logic changes.
  - No compose/task orchestration implementation in this change.

## Validation Results

- `python -m pytest -q` -> `pass` (`469 passed, 11 warnings`)
- `npm --prefix client run build` -> `pass` (`vite build completed successfully`)
- `python -m compileall src main.py` -> `pass` (completed without errors)
- `rg -n "run_true_tests\.py"` -> `pass` (remaining references are decision/minor context only)

## Contract and Compatibility

- Contract/API changes: `none`
- Migration/state changes: `none`
- Backward compatibility: Documentation-only; existing runtime behavior unchanged.

## Metrics (if applicable)

- Baseline:
  - N/A (docs-only change)
- After:
  - N/A (docs-only change)

## Risks

- Root README command surface can drift if future runtime commands change.
- Non-archived planning docs may reintroduce stale commands unless reviewed in future doc updates.

## Rollback Plan

- Fast disable path: Revert `README.md` and doc updates in this change set.
- Full revert path: Revert the commit containing this docs-only scope.

## Follow-up Work

- `67-add-dev-runtime-preflight-and-command-surface.md`
- `46-operationalize-dev-runtime-with-compose-and-tasks.md`
