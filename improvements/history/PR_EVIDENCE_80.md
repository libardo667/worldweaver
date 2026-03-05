# PR Evidence: Minor 80 - Structured Logging and Request Correlation IDs

## Item

`improvements/minors/archive/80-add-structured-logging-and-request-correlation-ids.md`

## Scope

Implemented correlation-aware request lifecycle logging and normalized core structured events without changing API contracts.

## What Changed

| File | Change |
|------|--------|
| `main.py` | Added HTTP middleware that binds correlation IDs per request, logs `request_start`/`request_end`, and returns `X-WW-Trace-Id` + `X-Correlation-Id` headers. |
| `src/services/llm_client.py` | Normalized LLM instrumentation events to `llm_call` and included both `trace_id` and `correlation_id`. |
| `src/services/runtime_metrics.py` | Added `correlation_id` to recorded LLM recent-event payloads when trace is present. |
| `src/api/game/action.py` | Switched to middleware-bound trace IDs for `/api/action` and `/api/action/stream`; preserved existing payload contracts. |
| `src/api/game/story.py` | Switched `/api/next` route to middleware-bound trace IDs; preserved existing payload contracts. |
| `src/api/game/turn.py` | Switched `/api/turn` route to middleware-bound trace IDs for consistency. |
| `src/services/turn_service.py` | Added structured `storylet_selected` and `state_committed` JSON events with correlation IDs. |
| `tests/api/test_trace_logging.py` | Added new coverage for correlation header propagation and structured lifecycle/core event trace consistency. |
| `improvements/ROADMAP.md` | Marked minor `80` complete and removed it from active pending queue. |

## Why This Matters

- It makes debugging deterministic: all logs from one request can be stitched together by a single correlation ID.
- It shortens incident triage time by exposing canonical lifecycle events (`request_start`, `request_end`, `llm_call`, `storylet_selected`, `state_committed`) in machine-parseable JSON.
- It improves comparative playtest and eval analysis quality because request-level traces now map reliably to turn-level behavior and LLM activity.

## Acceptance Criteria Check

- [x] Every API request receives a correlation ID and response header.
- [x] Logs for core request lifecycle stages include the same correlation ID.
- [x] Existing route behavior and payload contracts remain unchanged.
- [x] Correlation propagation tests pass.

## Quality Gate Evidence

### Gate 1: Contract Integrity

- No route path changes.
- No request/response schema changes for `/api/next`, `/api/action`, `/api/action/stream`, `/api/turn`.

### Gate 2: Correctness

- `python -m pytest tests/api/test_trace_logging.py -q` -> `4 passed`
- `python -m pytest tests/api/test_action_endpoint.py -q` -> `27 passed`
- `python -m pytest tests/api/test_game_endpoints.py -q` -> `45 passed`
- `python -m pytest -q` -> `539 passed, 14 warnings`

### Gate 3: Build and Static Health

- `python scripts/dev.py lint-all` -> pass
- `npm --prefix client run build` -> pass

### Gate 5: Operational Safety

- Rollback path: revert this PR (middleware + route + logging changes).
- No database migration required.
- No irreversible state/data transform introduced.

## Residual Risk

- Request lifecycle logging for streaming responses records route-dispatch completion timing; stream-body completion timing remains separately logged in route-level timing events.
- Existing non-JSON legacy logs still exist in some modules; this change normalizes critical path events but does not convert all logs in the codebase.
