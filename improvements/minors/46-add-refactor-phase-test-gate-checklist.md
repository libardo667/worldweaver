# Add a refactor phase test-gate checklist for repeatable execution

## Problem

The refactor plan requires tests to pass at the end of each phase, but there is no explicit checklist artifact in the repository to enforce this cadence.

## Proposed Solution

1. Add a concise checklist doc for refactor phase execution.
2. Include required commands:
   - `pytest -q`
   - optional targeted reruns (for example `pytest tests/api -q`)
3. Include a per-phase done template (phase name, commit hash, test outputs).

## Files Affected

- `improvements/refactor_phase_checklist.md` (new)

## Acceptance Criteria

- [ ] Checklist file exists and maps directly to phases 0-7.
- [ ] Required test gate commands are documented once and reused.
- [ ] Refactor contributors can record pass/fail per phase in one place.
