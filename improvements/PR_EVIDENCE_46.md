# PR Evidence

## Change Summary

- Item ID(s): `46-operationalize-dev-runtime-with-compose-and-tasks`
- PR Scope: Added a canonical single-command local runtime stack using Docker Compose, expanded the `scripts/dev.py` task surface for install/start/stop/log/reset flows, and updated contributor docs/env defaults while preserving manual fallback workflows.
- Risk Level: `medium`

## Behavior Impact

- User-visible changes:
  - New single-command stack path: `python scripts/dev.py stack-up`.
  - New runtime task commands in `scripts/dev.py` (`install`, `stack-up`, `stack-down`, `stack-logs`, `reset-data`).
  - Updated runtime docs in `README.md` and `client/README.md`.
- Non-user-visible changes:
  - Added `docker-compose.yml`, backend `Dockerfile`, client `client/Dockerfile`, and `.dockerignore`.
  - Client proxy target can now be overridden via `VITE_PROXY_TARGET` (defaults preserved for non-containerized local dev).
- Explicit non-goals:
  - No API route/path/payload contract changes.
  - No schema migrations or persistent telemetry additions.

## Validation Results

- `python scripts/dev.py preflight` -> `pass`
- `python scripts/dev.py test` -> `pass` (`479 passed, 12 warnings`)
- `python scripts/dev.py build` -> `pass`
- `python -m pytest -q` -> `pass` (`479 passed, 12 warnings`)
- `npm --prefix client run build` -> `pass`
- Compose smoke:
  - `python scripts/dev.py stack-up` -> `pass`
  - `http://localhost:8000/health` -> `200`
  - `http://localhost:5173` -> `200`
  - `python scripts/dev.py stack-down` -> `pass`

## Contract and Compatibility

- Contract/API changes: `none`
- Migration/state changes: `none`
- Backward compatibility: Manual two-process runtime remains supported and documented.

## Metrics (if applicable)

- Baseline:
  - No canonical one-command backend+client orchestration artifact.
- After:
  - Canonical task-surface + compose runtime path available with health checks and documented ports.

## Risks

- Docker volume mounts and dependency caches can behave differently across host OS setups.
- Compose and host/manual workflows can drift if docs/task-surface are not kept aligned.
- Existing warning baseline remains in test output and is tracked separately.

## Rollback Plan

- Fast disable path: use manual fallback (`python scripts/dev.py backend` and `python scripts/dev.py client`).
- Full revert path: revert this PR's compose/runtime-orchestration changes.
- Data rollback: no irreversible state changes; local sqlite files can be removed with `python scripts/dev.py reset-data --yes`.

## Follow-up Work

- `65-add-constellation-graph-view-v1.md`
- `50-establish-full-project-lint-baseline-and-ci-gates.md`
