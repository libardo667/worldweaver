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
5. Document one recommended “happy path” for new contributors and one minimal fallback path.

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

- [ ] A new contributor can boot the full dev stack with one documented command path.
- [ ] Backend and client are reachable with documented default ports and proxy behavior.
- [ ] Startup fails fast with clear messaging when required environment variables are missing.
- [ ] Existing manual runtime flow remains supported and documented as fallback.
- [ ] `python -m pytest -q` and `npm --prefix client run build` remain runnable from the task surface.
- [ ] No API route or payload contract changes are introduced by this operationalization.

## Risks & Rollback

Container setup can add complexity (volume mounts, platform differences, dependency cache churn). Roll back by retaining all existing manual commands and disabling Compose as the recommended default while keeping documentation and scripts optional.

