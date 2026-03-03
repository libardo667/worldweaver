# PR Evidence

## Change Summary

- Item ID(s): `42-add-world-projection-backfill-command`, `43-add-session-bootstrap-endpoint-with-goal`, `46-add-refactor-phase-test-gate-checklist`
- PR Scope: Completed the roadmap close-out sweep after minor `49` by verifying acceptance for minors `42`, `43`, and `46`, filling the remaining projection rebuild session-scope gap in minor `42`, and moving all three minor docs from active queue to archive while updating roadmap status.
- Risk Level: `low`

## Behavior Impact

- User-visible changes:
  - `scripts/rebuild_projection.py` now supports `--session-id` for session-scoped projection replay.
- Non-user-visible changes:
  - `rebuild_world_projection` now supports optional session-scoped rebuild and targeted projection row clearing.
  - Added regression coverage for session-scoped rebuild behavior.
  - Archived completed minor docs `42`, `43`, and `46` and updated roadmap queues/order.
- Explicit non-goals:
  - No API route/path/payload contract changes.
  - No runtime orchestration changes from major `46`.

## Validation Results

- `python -m pytest -q tests/service/test_world_memory.py -k rebuild_projection` -> `blocked` (`ImportError: datetime.UTC` under Python 3.10 runtime in this environment)
- `python scripts/dev.py verify` -> `blocked` (`ImportError: datetime.UTC` during test collection under Python 3.10 runtime)
- `python -m compileall src/services/world_memory.py scripts/rebuild_projection.py tests/service/test_world_memory.py` -> `pass`
- `PYTHONPATH=. python scripts/rebuild_projection.py --help` -> `pass`
- `python - <<'PY' ... rebuild_world_projection(..., session_id=...) ... PY` -> `pass` (in-memory SQLAlchemy smoke check for scoped replay)

## Contract and Compatibility

- Contract/API changes: `none`
- Migration/state changes: `none`
- Backward compatibility: Existing projection rebuild behavior remains default (full replay); session-scoped replay is additive.

## Metrics (if applicable)

- Baseline:
  - N/A
- After:
  - N/A

## Risks

- Session-scoped rebuild correctness assumes projection rows can be mapped by `source_event_id`; manual projection edits outside event replay remain out-of-scope.
- Projection key collisions across sessions still represent shared-world overwrite semantics by event ordering.

## Rollback Plan

- Fast disable path: Avoid `--session-id` usage and continue full rebuild mode.
- Full revert path: Revert this commit to restore previous full-rebuild-only behavior and roadmap/minor state.

## Follow-up Work

- `44-add-llm-latency-and-token-usage-metrics.md`
- `46-operationalize-dev-runtime-with-compose-and-tasks.md`
