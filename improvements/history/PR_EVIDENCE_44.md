# PR Evidence

## Change Summary

- Item ID(s): `44-add-llm-latency-and-token-usage-metrics`
- PR Scope: Added structured LLM latency/token instrumentation in runtime service paths, introduced in-memory aggregate route metrics for `/api/next` and `/api/action`, and exposed a dev-gated debug metrics endpoint.
- Risk Level: `low`

## Behavior Impact

- User-visible changes:
  - New debug endpoint `GET /api/debug/metrics` (available when `enable_dev_reset` is true).
- Non-user-visible changes:
  - LLM call metrics now emit structured logs from `llm_service` and `command_interpreter`.
  - Route-level aggregate metrics now collect request count/latency and attributed LLM token usage.
- Explicit non-goals:
  - No changes to existing `/api/next` or `/api/action` request/response schemas.
  - No persistent telemetry backend integration.

## Validation Results

- `python -m pytest -q tests/service/test_llm_service.py tests/service/test_command_interpreter.py tests/api/test_game_endpoints.py` -> `pass` (`98 passed, 9 warnings`)
- `python -m pytest -q` -> `pass` (`479 passed, 12 warnings`)
- `npm --prefix client run build` -> `pass` (`tsc --noEmit` + `vite build`)

## Contract and Compatibility

- Contract/API changes: additive `GET /api/debug/metrics`; no payload changes to existing routes.
- Migration/state changes: none.
- Backward compatibility: preserved for existing clients.

## Metrics (if applicable)

- Baseline:
  - Request timing logs existed; no in-process aggregate surface for `/api/next` and `/api/action`.
- After:
  - Structured per-call LLM metrics include `duration_ms`, `status`, `model`, and token counts when available.
  - `GET /api/debug/metrics` reports route and recent LLM aggregates without secrets.

## Risks

- Metrics are process-local and reset on restart.
- Multi-worker deployments will require external aggregation for global totals.
- Existing warning baseline remains in test output and is tracked separately.

## Rollback Plan

- Fast disable path: set `enable_dev_reset=false` to hide `GET /api/debug/metrics`.
- Full revert path: revert the metrics instrumentation and endpoint commit(s).
- Data rollback: none required (no schema/state migration).

## Follow-up Work

- `46-operationalize-dev-runtime-with-compose-and-tasks.md`
- `65-add-constellation-graph-view-v1.md`
- `50-establish-full-project-lint-baseline-and-ci-gates.md`
