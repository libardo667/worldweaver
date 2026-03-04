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

## Files Affected

- `scripts/eval_narrative.py`
- `tests/integration/narrative_eval_scenarios.json`
- `reports/narrative_eval/baseline.json`
- `tests/integration/test_narrative_eval_harness.py`

## Acceptance Criteria

- [ ] Harness emits contradiction and arc-adherence metrics in `latest.json`.
- [ ] Baseline threshold file includes the new metrics.
- [ ] Smoke harness test validates presence of new metric keys.
- [ ] `python scripts/dev.py eval-smoke` passes with enforcement enabled.

