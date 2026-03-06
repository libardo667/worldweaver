# Add projection and clarity metrics to harness artifacts

## Problem
Current run and sweep artifacts capture latency, failures, prefix repetition, and motif reuse, but they do not expose v3 projection behavior. This leaves planner quality and speculative waste largely invisible.

## Proposed Solution
Add projection-specific metrics to run and sweep summaries.

- Per-run metrics: `projection_stub_count`, `projection_hit_rate`, `projection_waste_rate`, `projection_veto_rate`, `clarity_level_distribution`.
- Phase aggregates: averaged and p95 projection metrics.
- Ranking support: include projection metrics in secondary ranking views without breaking existing composite score paths.

## Files Affected
- `playtest_harness/long_run_harness.py`
- `playtest_harness/parameter_sweep.py`
- `tests/integration/test_parameter_sweep_harness.py`

## Acceptance Criteria
- [ ] New projection metrics are present in run summaries.
- [ ] Phase summaries aggregate projection metrics across configs/runs.
- [ ] Existing summary consumers remain compatible (additive fields).
- [ ] Regression tests validate field presence and types.
