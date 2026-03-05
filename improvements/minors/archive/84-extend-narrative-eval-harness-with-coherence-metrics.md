# Extend narrative evaluation harness with contradiction and arc-adherence coherence metrics

## Problem

Current narrative harness metrics focus on memory carryover, divergence, command
success, and repetition. It does not explicitly score contradiction frequency or
goal/arc adherence drift.

## Proposed Solution

Add low-cost coherence checks to the existing harness:

1. Add contradiction detection metric over scenario turn outputs/world facts.
2. Add arc-adherence metric that measures drift from declared goal progression.
3. Add repetition-window guard metric (same storylet/beat too soon).
4. Update baseline thresholds and smoke integration test assertions.

## Scope Boundaries

- Keep eval harness deterministic and runnable without live LLM credentials.
- Do not change API payload contracts; only consume existing routes for signals.
- Keep metric additions additive (new keys), not renaming/removing existing metrics.

## Assumptions

- Existing smoke scenarios are sufficient to exercise new metric computation paths.
- Arc adherence can be inferred from declared goals plus persisted arc/state signals.
- Contradiction checks are directional signals (heuristic), not formal logical proofs.

## Files Affected

- `scripts/eval_narrative.py`
- `tests/integration/narrative_eval_scenarios.json`
- `reports/narrative_eval/baseline.json`
- `tests/integration/test_narrative_eval_harness.py`

## Acceptance Criteria

- [x] Harness emits contradiction and arc-adherence metrics in `latest.json`.
- [x] Baseline threshold file includes the new metrics.
- [x] Smoke harness test validates presence of new metric keys.
- [x] `python scripts/dev.py eval-smoke` passes with enforcement enabled.

## Validation Commands

- `python scripts/dev.py eval-smoke`
- `python -m pytest tests/integration/test_narrative_eval_harness.py -q`
- `python scripts/dev.py lint-all`
- `python -m pytest -q`
- `npm --prefix client run build`

## Rollback Notes

- Revert eval-harness metric additions and fixture/baseline updates in this item.
- No migration/state schema changes were introduced; rollback is code-only.
