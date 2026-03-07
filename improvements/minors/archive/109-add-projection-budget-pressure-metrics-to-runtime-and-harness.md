# Add projection budget pressure metrics to runtime and harness

## Problem
Projection tuning lacks enough pressure-level diagnostics to explain why budget exhaustion occurs or which pruning choices trade off coherence for latency.

## Proposed Solution
Add additive runtime/harness metrics that expose projection budget pressure and pruning outcomes.

- Emit per-turn metrics for pressure tier, nodes considered, nodes pruned, and prune reason distribution.
- Surface budget-exhaustion cause breakdown (time, node cap, depth cap, disabled path).
- Add harness artifact fields for projection utility vs. spend analysis.

## Files Affected
- `src/services/prefetch_service.py`
- `src/services/runtime_metrics.py`
- `tests/service/test_prefetch_service.py`
- `tests/integration/test_parameter_sweep_harness.py`
- `improvements/harness/templates/PR_EVIDENCE_TEMPLATE.md`

## Acceptance Criteria
- [ ] Runtime metrics expose projection pressure and prune distribution fields.
- [ ] Harness artifacts include budget-cause and utility-vs-spend summaries.
- [ ] Existing route contracts remain additive and backward compatible.
- [ ] Tests validate metric field presence and type stability.

## Validation Commands
- `pytest -q tests/service/test_prefetch_service.py tests/integration/test_parameter_sweep_harness.py`
- `python scripts/dev.py quality-strict`
