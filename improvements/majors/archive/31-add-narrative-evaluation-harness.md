# Add a narrative evaluation harness and regression gates

## Problem

`VISION.md` defines concrete success outcomes (memory persistence, divergent playthroughs, coherent freeform responses), but the codebase has no repeatable evaluation harness to measure progress. We cannot reliably tell whether major changes improve or regress the intended experience.

## Proposed Solution

1. Create deterministic evaluation scenarios with fixed seeds and scripted turns.
2. Implement evaluation metrics and reports:
   - memory carryover score
   - divergence score between parallel playthroughs
   - freeform coherence checks against world facts
   - stall/repetition frequency
3. Add a test/eval command that runs locally and in CI.
4. Store evaluation outputs as machine-readable artifacts for trend tracking.
5. Set baseline thresholds and fail CI when regressions exceed tolerance.

## Files Affected

- `scripts/eval_narrative.py` (new)
- `tests/integration/narrative_eval_scenarios.json` (new)
- `tests/integration/test_narrative_eval_harness.py` (new)
- `scripts/dev.py`
- `README.md`
- `improvements/HARNESS_BOOTSTRAP_CHECKLIST.md`
- `.github/workflows/narrative-eval-smoke.yml` (new CI hook)
- `reports/narrative_eval/*` (baseline + generated evaluation artifacts)

## Assumptions

- Evaluation should be deterministic and runnable without live LLM credentials.
- Smoke CI gate should use a reduced scenario subset to keep runtime bounded.
- Metrics are directional product-health signals and do not replace qualitative review.

## Validation Commands

- `python scripts/eval_narrative.py --smoke --enforce`
- `python scripts/eval_narrative.py --enforce`
- `python -m pytest -q`
- `npm --prefix client run build`

## Acceptance Criteria

- [x] Evaluation command runs end-to-end against test DB fixtures.
- [x] Reports include all agreed metrics with comparable baselines.
- [x] CI can run a smoke subset and flag regressions.
- [x] At least one metric directly maps to each success criterion in `VISION.md`.
- [x] Team can inspect trend history across commits.

## Risks & Rollback

Narrative quality is partly subjective, so metrics may overfit. Keep objective checks small and transparent, and treat scores as directional signals. Roll back CI gates to warning-only mode if false positives block development.
