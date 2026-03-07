# Add graph-fact dedupe and canonical-entity audit command

## Problem
When fact extraction drifts, duplicate entities/predicates can accumulate silently and degrade world-graph quality over time.

## Proposed Solution
Add an audit command that scans graph/fact tables for canonicalization and dedupe anomalies.

- Add a developer command to report duplicate entity keys, near-duplicate predicates, and orphan fact links.
- Emit a machine-readable report for CI/harness consumption.
- Provide optional dry-run remediation recommendations without mutating data by default.

## Files Affected
- `scripts/dev.py`
- `src/services/world_memory.py`
- `tests/service/test_world_memory.py`
- `improvements/harness/04-QUALITY_GATES.md`

## Acceptance Criteria
- [ ] Audit command returns deterministic duplicate/anomaly counts.
- [ ] Report output is machine-readable and includes remediation guidance.
- [ ] Command is safe by default (read-only unless explicit apply flag is introduced later).
- [ ] Tests cover normal, duplicate-heavy, and malformed graph snapshots.

## Validation Commands
- `pytest -q tests/service/test_world_memory.py`
- `python scripts/dev.py quality-strict`
