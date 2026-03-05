# PR Evidence

## Change Summary

- Item ID(s): `61`
- PR Scope: Unified turn sequencing by introducing `TurnOrchestrator` in `src/services/turn_service.py`, routing `/api/next` and `/api/action` through shared orchestration phases, and adding optional feature-flagged `/api/turn` without changing existing legacy endpoint contracts.
- Risk Level: `medium`

## Behavior Impact

- User-visible changes:
  - Optional `/api/turn` endpoint is available when `WW_ENABLE_TURN_ENDPOINT=1`.
- Non-user-visible changes:
  - `/api/next` and `/api/action` now delegate core sequencing to one shared service.
  - Shared turn pipeline now consistently handles reducer commit, simulation tick, story/content selection, and persistence paths.
- Explicit non-goals:
  - No request/response contract changes for existing `/api/next`, `/api/action`, or `/api/action/stream` routes.

## Validation Results

- `python -m pytest tests/api/test_game_endpoints.py tests/api/test_action_endpoint.py tests/api/test_turn_endpoint.py -q` -> pass (`70 passed`)
- `python -m pytest -q` -> pass (`507 passed`)
- `npm --prefix client run build` -> pass (`vite build completed`)

## Contract and Compatibility

- Contract/API changes: Added optional `/api/turn` only (feature-flagged, default off).
- Migration/state changes: none.
- Backward compatibility: existing `/api/next` and `/api/action` payloads and behavior preserved; integration tests pass.

## Metrics (if applicable)

- Baseline:
  - Not captured in this PR (functional parity change).
- After:
  - Not captured in this PR (functional parity change).

## Risks

- Shared orchestrator centralizes critical turn flow; regressions could affect both `/api/next` and `/api/action`.
- `/api/turn` is new surface area and may need additional client hardening before broad enablement.

## Rollback Plan

- Fast disable path: set `WW_ENABLE_TURN_ENDPOINT=0` to disable `/api/turn`.
- Full revert path:
  - Revert commit(s) touching `src/services/turn_service.py`, `src/api/game/story.py`, `src/api/game/action.py`, `src/api/game/turn.py`, and `src/api/game/__init__.py`.
  - Keep legacy `/api/next` and `/api/action` handlers (pre-delegation state).

## Follow-up Work

- Add side-by-side telemetry comparison between legacy and unified turn paths during rollout.
- Add targeted load/perf profiling for shared orchestrator hot paths.
