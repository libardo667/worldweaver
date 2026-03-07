# Operationalize v3 model-lane matrix and projection-budget sweeps

## Problem
Current sweeps tune primarily narrator-facing parameters. v3 introduces planner lane behavior and projection budgets that must be measured head-to-head with deterministic seeds. Without a dedicated evaluation path, lane tradeoffs in coherence, motif diversity, and latency cannot be trusted.

## Proposed Solution
Extend existing harness/sweep paths (no parallel runtime path) so lane and budget experiments are first-class and reproducible.

### Phase 1: Lane-matrix and budget axes
1. Extend sweep config generation in `playtest_harness/parameter_sweep.py` with explicit axes for:
   - scene narrator model,
   - planner/referee model,
   - projection budget envelope (depth, node limit, time budget).
2. Keep defaults equivalent to current behavior when axes are not provided, preserving backward compatibility.
3. Thread selected lane/budget values into run config/env overrides consumed by `playtest_harness/long_run_harness.py`.

### Phase 2: Deterministic fairness guards
1. Centralize per-phase seed scheduling so every compared config uses the same seed list.
2. Persist seed schedule in phase summaries/manifests for replay.
3. Add guard checks that fail fast when compared configs deviate from shared seed sets.

### Phase 3: Metrics and ranking operationalization
1. Build on current projection metrics by adding lane-matrix visibility:
   - lane/budget settings per run,
   - projection quality metrics (hit/waste/veto),
   - clarity distribution and fallback-reason distribution.
2. Keep existing composite score path stable.
3. Add/retain secondary ranking views for projection quality and motif quality to support multi-objective review.

### Phase 4: Command-surface and quality-gate integration
1. Extend `scripts/dev.py` under `python scripts/dev.py harness ...` with lane-matrix sweep entrypoints/examples.
2. Update `improvements/harness/04-QUALITY_GATES.md` with required v3 sweep evidence fields and minimum reproducibility checks.

### Phase 5: Test hardening
1. Add integration coverage for:
   - lane/budget axis expansion shape,
   - deterministic seed parity across compared configs,
   - manifest field shape,
   - deterministic secondary ranking behavior for projection quality.
2. Keep tests contract-focused (public summary payloads and CLI outputs), not internal incidental implementation details.

Planned validation commands for implementation:
- `python -m pytest tests/integration/test_parameter_sweep_harness.py`
- `python -m pytest tests/integration/test_parameter_sweep_phase_a.py tests/integration/test_parameter_sweep_ranking.py tests/integration/test_parameter_sweep_metrics.py tests/integration/test_turn_progression_simulation.py`
- `python scripts/dev.py quality-strict`

## Files Affected
- `playtest_harness/parameter_sweep.py`
- `playtest_harness/long_run_harness.py`
- `scripts/dev.py`
- `tests/integration/test_parameter_sweep_harness.py` (new)
- `tests/integration/test_turn_progression_simulation.py`
- `tests/integration/test_parameter_sweep_phase_a.py`
- `tests/integration/test_parameter_sweep_ranking.py`
- `tests/integration/test_parameter_sweep_metrics.py`
- `improvements/harness/04-QUALITY_GATES.md`

## Acceptance Criteria
- [ ] Sweep CLI can vary narrator lane, referee lane, and projection budget parameters.
- [ ] Phase summaries include v3 projection quality metrics and ranking views.
- [ ] Compared configs in the same run use identical seed sets.
- [ ] Manifest captures lane matrix parameters and projection budget settings.
- [ ] Integration tests cover deterministic ranking and summary/manifest field shape.
- [ ] Existing sweep consumers remain compatible (additive fields only, no required field removals).

## Risks & Rollback
- Risk: expanded search space increases sweep runtime and cost.
- Risk: ranking instability if quality weights are not calibrated.
- Risk: lane-axis wiring could accidentally alter default-path harness behavior when no lane overrides are provided.
- Rollback: restrict sweeps to narrator-only parameters and disable lane/budget axes via `scripts/dev.py harness` defaults while preserving existing summary formats.
- Rollback: revert lane-axis CLI/env plumbing in `scripts/dev.py` + `playtest_harness/parameter_sweep.py` first; keep additive metric fields in summaries if already consumed.
