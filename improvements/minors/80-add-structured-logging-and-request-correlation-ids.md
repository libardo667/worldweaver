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

## Files Affected

- `main.py`
- `src/services/llm_client.py`
- `src/services/runtime_metrics.py`
- `src/api/game/action.py`
- `src/api/game/story.py`
- `tests/api/test_trace_logging.py` (new)

## Acceptance Criteria

- [ ] Every API request receives a correlation ID and response header.
- [ ] Logs for core request lifecycle stages include the same correlation ID.
- [ ] Existing route behavior and payload contracts remain unchanged.
- [ ] Correlation propagation tests pass.

