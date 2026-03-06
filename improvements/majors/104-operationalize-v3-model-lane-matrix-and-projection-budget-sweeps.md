# Operationalize v3 model-lane matrix and projection-budget sweeps

## Problem
Current sweeps tune primarily narrator-facing parameters. v3 introduces planner lane behavior and projection budgets that must be measured head-to-head with deterministic seeds. Without a dedicated evaluation path, lane tradeoffs in coherence, motif diversity, and latency cannot be trusted.

## Proposed Solution
Extend harness and sweep execution to treat model lanes and projection budgets as first-class experiment axes.

1. Add lane matrix support for narrator model, referee/planner model, and projection expansion budgets.
2. Require fixed-seed sets across compared configs to keep evaluations fair.
3. Record v3-specific metrics (projection hit rate, projection waste rate, veto rate, clarity distribution, fallback reasons).
4. Add summary ranking views for latency, failure, and projection quality metrics.
5. Produce reproducible manifests with lane settings, budgets, and quality-gate outcomes.

## Files Affected
- `playtest_harness/parameter_sweep.py`
- `playtest_harness/long_run_harness.py`
- `scripts/dev.py`
- `tests/integration/test_parameter_sweep_harness.py`
- `tests/integration/test_turn_progression_simulation.py`
- `improvements/harness/04-QUALITY_GATES.md`

## Acceptance Criteria
- [ ] Sweep CLI can vary narrator lane, referee lane, and projection budget parameters.
- [ ] Phase summaries include v3 projection quality metrics and ranking views.
- [ ] Compared configs in the same run use identical seed sets.
- [ ] Manifest captures lane matrix parameters and projection budget settings.
- [ ] Integration tests cover deterministic ranking and summary field shape.

## Risks & Rollback
- Risk: expanded search space increases sweep runtime and cost.
- Risk: ranking instability if quality weights are not calibrated.
- Rollback: restrict sweeps to narrator-only parameters and disable projection-budget axes while preserving existing summary formats.
