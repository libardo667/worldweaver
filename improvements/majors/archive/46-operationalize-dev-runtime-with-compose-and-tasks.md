# Operationalize local runtime with a single-command dev stack

## Problem

Local runtime requires multiple manual steps across backend and client processes (`uvicorn main:app --reload` + `npm run dev`) and depends on implicit environment setup. This slows onboarding, increases configuration drift, and makes reproducible testing harder across machines.

Current project assets include runtime docs and scripts, but no canonical dev orchestration artifact (no Compose/task entrypoint) and no single source of truth for startup/teardown commands.

## Proposed Solution

Establish a canonical local runtime interface that supports both containerized and non-containerized workflows while preserving existing API behavior.

1. Add a Compose-based dev stack for backend and client with explicit env wiring, ports, and health checks.
2. Add a task entrypoint surface (for example `Makefile` plus Windows-friendly script parity) for:
   - install dependencies
   - start/stop stack
   - run backend tests
   - run client build checks
   - reset local dev data safely
3. Standardize startup prerequisites and environment validation:
   - required API key variables
   - optional DB path overrides
   - feature-flag defaults
4. Preserve existing direct-run workflows as fallback (manual `uvicorn`/`npm` still valid).
5. Document one recommended "happy path" for new contributors and one minimal fallback path.

## Scope Boundaries

- No API route, request, response, or schema changes.
- Runtime orchestration only (containers, scripts, docs, and env wiring).
- No production deployment topology changes in this item.
- No lint-baseline remediation work from major `50` in this item.

## Assumptions

- Docker Desktop (or equivalent) is available for the canonical stack path.
- Existing `scripts/dev.py` remains the canonical cross-platform task surface.
- Local DB persistence remains SQLite file-based for development.
- Missing API key should fail fast on canonical startup paths but manual fallback remains available.

## Files Affected

- `docker-compose.yml` (new)
- `Dockerfile` (new, backend)
- `client/Dockerfile` (new)
- `Makefile` (new) and/or `scripts/dev-*.ps1` / `scripts/dev-*.sh` (new)
- `README.md` (if absent today, create; otherwise update)
- `client/README.md`
- `.env.example`
- `scripts/*` (selected helper scripts for preflight/reset)

## Acceptance Criteria

- [x] A new contributor can boot the full dev stack with one documented command path.
- [x] Backend and client are reachable with documented default ports and proxy behavior.
- [x] Startup fails fast with clear messaging when required environment variables are missing.
- [x] Existing manual runtime flow remains supported and documented as fallback.
- [x] `python -m pytest -q` and `npm --prefix client run build` remain runnable from the task surface.
- [x] No API route or payload contract changes are introduced by this operationalization.

## Validation Commands

- `python scripts/dev.py preflight`
- `python scripts/dev.py test`
- `python scripts/dev.py build`
- `python -m pytest -q`
- `npm --prefix client run build`

## Risks & Rollback

Container setup can add complexity (volume mounts, platform differences, dependency cache churn). Roll back by retaining all existing manual commands and disabling Compose as the recommended default while keeping documentation and scripts optional.

## Rollback Discipline

- Commit rollback: revert commit(s) introducing Compose/runtime task-surface artifacts.
- Fast disable path: use manual fallback (`python scripts/dev.py backend` + `python scripts/dev.py client`) and skip `stack-up`.
- Irreversible state: none expected (no migrations); local SQLite files can be removed via reset task.

## Closure Evidence (2026-03-03)

- Added Compose runtime artifacts:
  - `docker-compose.yml`
  - `Dockerfile` (backend)
  - `client/Dockerfile`
- Added task-surface commands to `scripts/dev.py`:
  - `install`
  - `stack-up`
  - `stack-down`
  - `stack-logs`
  - `reset-data` (safe, `--yes` required)
- Updated runtime documentation and env defaults in:
  - `README.md`
  - `client/README.md`
  - `.env.example`
- Preserved manual fallback runtime (`backend` / `client` commands and direct `uvicorn`/`npm run dev` paths).
- No API route or payload contract changes were introduced.

### Validation Results

- `python scripts/dev.py preflight` -> `pass`
- `python scripts/dev.py test` -> `pass` (`479 passed, 12 warnings`)
- `python scripts/dev.py build` -> `pass`
- `python -m pytest -q` -> `pass` (`479 passed, 12 warnings`)
- `npm --prefix client run build` -> `pass`
- Compose runtime smoke:
  - `python scripts/dev.py stack-up` -> `pass`
  - `http://localhost:8000/health` -> `200`
  - `http://localhost:5173` -> `200`
  - `python scripts/dev.py stack-down` -> `pass`
