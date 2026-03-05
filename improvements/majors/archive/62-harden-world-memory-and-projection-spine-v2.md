# Harden world memory, fact graph, and projection spine (v2)

## Problem
Archived majors `52`, `53`, and `54` established the initial memory/projection/grounding spine, but the current comparative playtest phase still required stricter deterministic evaluation coverage for identity convergence and grounding drift. The existing eval harness had a brittle identity assertion path and did not yet gate the expanded scenario/probe set mined from long runs.

## Scope Boundaries
- In scope: eval harness logic, scenario definitions, world-memory canonical identity normalization, baseline thresholds, and targeted tests for the new checks.
- Out of scope: API contract changes, frontend changes, and non-additive schema/migration changes.

## Assumptions
- Comparative playtest quality should be gated by deterministic harness metrics, not ad hoc transcript review.
- Existing route contracts and reducer behavior stay unchanged for this major.
- Identity convergence checks can be implemented as harness-level post-run assertions against the world graph.

## Proposed Solution
- Harden `scripts/eval_narrative.py` identity assertions to run directly against the deterministic eval DB session.
- Expand `tests/integration/narrative_eval_scenarios.json` with mined grounding probes and identity-convergence scenarios.
- Add rank/honorific canonicalization for world-node identity keys to improve alias convergence (`Silas Vane` vs `Warden Silas Vane`).
- Gate the new eval surface with updated baseline thresholds and integration/unit coverage.

## Files Affected
- `scripts/eval_narrative.py`
- `tests/integration/narrative_eval_scenarios.json`
- `tests/integration/test_narrative_eval_harness.py`
- `src/services/world_memory.py`
- `tests/service/test_world_memory.py`
- `reports/narrative_eval/baseline.json`
- `reports/narrative_eval/latest.json`
- `reports/narrative_eval/history.jsonl`

## Validation Commands
- `python scripts/dev.py eval-smoke`
- `python scripts/dev.py eval`
- `python -m pytest tests/integration/test_narrative_eval_harness.py -q`
- `python -m pytest tests/service/test_world_memory.py -q`
- `python -m pytest -q`
- `python scripts/dev.py lint-all`
- `npm --prefix client run build`

## Acceptance Criteria
- [x] v2 world-memory/projection hardening includes deterministic identity convergence checks in narrative eval.
- [x] Expanded narrative eval scenario/probe set executes and passes with `--enforce` using committed thresholds.
- [x] Alias canonicalization for rank-prefixed identities is covered by service tests.
- [x] `python -m pytest -q` succeeds.
- [x] Static/build gates (`lint-all`, client build) succeed.

## Risks & Rollback
- Risk: identity normalization may over-merge some edge-case names that begin with honorific-like tokens.
- Rollback: revert the world-memory normalization change and eval-harness identity assertion/scenario updates in this major.
- Safe-disable path: remove `identity_stability_score` threshold from `reports/narrative_eval/baseline.json` to unblock eval enforcement while preserving other gates.
