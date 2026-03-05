# Make author generation pipeline transaction-safe across commit, coordinate assignment, and auto-improvement

## Problem

Author flows (`/author/generate-world`, `/author/generate-intelligent`,
`/author/populate`) execute multi-step writes and post-processing across several
services. Failures in later stages can leave partially written storylets,
incomplete coordinate assignment, or half-applied auto-improvement outputs.

## Proposed Solution

Introduce explicit transaction boundaries and rollback policy for author flows:

1. Centralize multi-step author mutations in an orchestrator service with a
   single transaction boundary where feasible.
2. Use nested transactions/savepoints for recoverable sub-steps (bulk insert,
   coordinate assignment, auto-improvement stages).
3. Add operation-level job receipts capturing:
   - started/completed/failed state,
   - counts inserted/updated/skipped,
   - rollback actions applied.
4. Ensure endpoints return safe, explicit failure details without leaving the DB
   in partial inconsistent state.
5. Add integration tests with forced failures at each phase.

## Scope Boundaries

- Keep existing `/author/*` route paths and baseline response keys stable.
- Add receipt metadata additively without removing current response fields.
- Keep changes focused to author generation/population/ingest orchestration paths.

## Assumptions

- Author generation can use larger transaction scopes than runtime turn endpoints.
- Auto-improvement is a best-effort phase that can be isolated from core insert/assign transactions.
- Existing tests that assert current response keys should continue to pass.

## Files Affected

- `src/api/author/world.py`
- `src/api/author/generate.py`
- `src/api/author/populate.py`
- `src/services/storylet_ingest.py`
- `src/services/auto_improvement.py`
- `src/services/spatial_navigator.py`
- `src/models/schemas.py`
- `tests/api/test_author_generation.py`
- `tests/integration/test_author_pipeline_transactions.py`

## Validation Commands

- `python -m pytest -q tests/api/test_author_generation.py tests/integration/test_author_pipeline_transactions.py`
- `python -m pytest -q`
- `npm --prefix client run build`

## Acceptance Criteria

- [x] Simulated failures during coordinate assignment or auto-improvement do not
      leave partially committed world-generation writes.
- [x] Author endpoints return operation receipts with phase-level outcomes.
- [x] Bulk author operations are atomic or clearly rollback-safe by documented
      policy.
- [x] Existing author route paths and core payload contracts remain unchanged.
- [x] `python -m pytest -q tests/api/test_author_generation.py
      tests/integration/test_author_pipeline_transactions.py` passes.

## Risks & Rollback

Risk: larger transaction scopes can increase lock duration and contention.

Rollback:

1. Keep orchestration refactor isolated so legacy endpoint flow can be restored.
2. If contention issues appear, split into bounded transactional phases while
   preserving receipt-based recovery.
3. Revert orchestrator integration and keep prior per-step writes as temporary
   fallback.
