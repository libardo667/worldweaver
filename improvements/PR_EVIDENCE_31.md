# PR Evidence

## Change Summary

- Item ID(s): `31-add-narrative-evaluation-harness`
- PR Scope: Added a deterministic narrative evaluation harness with scripted scenarios, baseline thresholds, report artifacts, a smoke CI workflow, and local command-surface integration (`scripts/dev.py eval|eval-smoke`), then archived the completed major doc.
- Risk Level: `medium`

## Behavior Impact

- User-visible changes:
  - None.
- Non-user-visible changes:
  - New evaluation command: `python scripts/eval_narrative.py`.
  - New smoke gate in CI: `.github/workflows/narrative-eval-smoke.yml`.
  - New machine-readable artifacts under `reports/narrative_eval/`.
  - New integration coverage for eval harness execution.
- Explicit non-goals:
  - No API payload/route behavior changes.
  - No model or prompt tuning changes to optimize metric scores.

## Validation Results

- `python scripts/eval_narrative.py --smoke --enforce` -> `pass`
- `python scripts/eval_narrative.py --enforce` -> `pass`
- `python -m pytest -q tests/integration/test_narrative_eval_harness.py` -> `pass` (`1 passed`)
- `python -m pytest -q` -> `pass` (`470 passed, 11 warnings`)
- `npm --prefix client run build` -> `pass`

## Contract and Compatibility

- Contract/API changes: `none`
- Migration/state changes: `none`
- Backward compatibility: Existing routes and response shapes are unchanged; harness is additive.

## Metrics (if applicable)

- Baseline:
  - `memory_carryover_score >= 1.0`
  - `divergence_score >= 0.2`
  - `freeform_coherence_score >= 0.66`
  - `stall_repetition_score >= 0.5`
  - `narrative_command_success_rate >= 1.0`
- After:
  - Full eval metrics from latest run:
  - `memory_carryover_score = 1.0`
  - `divergence_score = 0.4`
  - `freeform_coherence_score = 0.666667`
  - `stall_repetition_score = 1.0`
  - `narrative_command_success_rate = 1.0`

## Risks

- Metrics are directional and can be gamed if interpreted as absolute quality scores.
- Threshold tuning may require follow-up to reduce false positives/negatives in CI.

## Rollback Plan

- Fast disable path: disable `narrative-eval-smoke` workflow or run without `--enforce`.
- Full revert path: revert this PR commit(s) to remove eval script, workflow, and report artifacts.

## Follow-up Work

- `50-establish-full-project-lint-baseline-and-ci-gates.md`
- `46-add-refactor-phase-test-gate-checklist.md`
