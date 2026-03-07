# Add state-domain contract tests and migration fixtures

## Problem
State-manager modularization is high-risk without a parity suite that locks down behavior for each domain boundary and legacy access pattern.

## Proposed Solution
Add focused tests/fixtures that enforce contract parity between legacy and modular state paths.

- Add domain-level invariant tests for inventory, relationships, environment, goals/arcs, and beats/history.
- Add migration fixtures that replay legacy session snapshots through the modularized loader path.
- Add shared assertion helpers for reducer-visible deltas to avoid duplicated test logic.

## Files Affected
- `tests/service/test_state_manager.py`
- `tests/service/test_reducer.py`
- `tests/fixtures/state/`
- `tests/helpers/state_assertions.py`

## Acceptance Criteria
- [ ] Domain invariants are covered with deterministic tests.
- [ ] Legacy session snapshots load and round-trip without behavior drift.
- [ ] Reducer-facing state delta expectations remain stable.
- [ ] Failing migrations produce actionable assertion output.

## Validation Commands
- `pytest -q tests/service/test_state_manager.py tests/service/test_reducer.py`
- `python scripts/dev.py quality-strict`
