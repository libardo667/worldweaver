# Add v3 smoke scenarios and gate commands for projection workflow

## Problem
Quality gates do not yet include targeted smoke validation for projection planner behavior, clarity diagnostics, and canonical commit boundaries.

## Proposed Solution
Extend test and gate docs with focused v3 smoke commands.

- Add projection workflow smoke tests covering planner generation, non-canon isolation, commit/invalidation, and additive diagnostics.
- Add a documented v3 gate command path for local and CI verification.
- Update quality gate notes to require these tests for v3-risk changes.

## Files Affected
- `tests/integration/test_turn_progression_simulation.py`
- `tests/integration/test_parameter_sweep_harness.py`
- `improvements/harness/04-QUALITY_GATES.md`
- `README.md`

## Acceptance Criteria
- [ ] Projection smoke tests exist and pass in local runs.
- [ ] Quality gate docs list v3-specific required checks.
- [ ] README exposes the v3 smoke command path.
- [ ] v3 items reference these checks in validation sections.
