# Add long-run soak scenarios for graph and projection drift

## Problem
Current gates are strong for unit/regression checks but under-represent multi-hundred-turn drift risks in graph cleanliness, projection cache churn, and fallback behavior.

## Proposed Solution
Add deterministic soak scenarios that stress graph extraction and projection invalidation/pruning over long turn sequences.

- Add long-run integration scenarios with controlled seeds and constrained model stubs.
- Capture graph-duplicate growth, fallback rates, projection invalidation counts, and budget-exhaustion rates.
- Add pass/fail thresholds for drift indicators and regressions.

## Files Affected
- `tests/integration/test_turn_progression_simulation.py`
- `tests/integration/test_parameter_sweep_harness.py`
- `improvements/harness/04-QUALITY_GATES.md`
- `improvements/history/` 

## Acceptance Criteria
- [ ] Soak scenarios run deterministically with reproducible seeds.
- [ ] Drift indicators are captured and compared against bounded thresholds.
- [ ] Regressions fail the soak gate with clear artifact output.
- [ ] Harness docs include the soak command path and interpretation notes.

## Validation Commands
- `pytest -q tests/integration/test_turn_progression_simulation.py tests/integration/test_parameter_sweep_harness.py`
- `python scripts/dev.py quality-strict`
