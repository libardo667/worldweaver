# Add structured logging and request correlation IDs across API and service calls

## Problem

Structured logging exists in parts of the codebase, but request-level
correlation is not uniformly enforced across all routes and service logs.
Tracing a full path (`request -> selector -> facts -> model -> commit`) remains
manual and inconsistent.

## Proposed Solution

Standardize correlation-aware structured logging:

1. Add request middleware that binds a correlation ID for every request and
   returns it in response headers.
2. Ensure service logs include the bound trace/correlation ID.
3. Normalize key log events (`request_start`, `request_end`, `llm_call`,
   `storylet_selected`, `state_committed`) as JSON payloads.
4. Add tests that verify correlation ID propagation and header behavior.

## Scope Boundaries

- Keep API payload contracts unchanged.
- Add correlation enforcement without changing endpoint paths.
- Restrict new logging normalization to request lifecycle and core turn/LLM events.

## Assumptions

- Existing `X-WW-Trace-Id` remains the primary public header contract.
- Adding `X-Correlation-Id` as an alias header is backward-compatible.
- Structured event names are additive and should not remove existing operational logs.

## Files Affected

- `main.py`
- `src/services/llm_client.py`
- `src/services/runtime_metrics.py`
- `src/api/game/action.py`
- `src/api/game/story.py`
- `src/api/game/turn.py`
- `src/services/turn_service.py`
- `tests/api/test_trace_logging.py` (new)

## Acceptance Criteria

- [x] Every API request receives a correlation ID and response header.
- [x] Logs for core request lifecycle stages include the same correlation ID.
- [x] Existing route behavior and payload contracts remain unchanged.
- [x] Correlation propagation tests pass.

## Validation Commands

- `python -m pytest tests/api/test_trace_logging.py -q`
- `python -m pytest tests/api/test_action_endpoint.py -q`
- `python -m pytest tests/api/test_game_endpoints.py -q`
- `python scripts/dev.py lint-all`
- `python -m pytest -q`
- `npm --prefix client run build`

## Rollback Notes

- Revert middleware + route trace plumbing changes to restore prior per-route trace behavior.
- Fast disable path is direct revert; no data migrations/state schema changes were introduced.
