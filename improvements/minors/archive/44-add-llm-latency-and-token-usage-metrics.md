# Add LLM latency and token usage metrics for runtime calls

## Problem

As runtime adaptation and synthesis increase, there is limited visibility into latency and token cost for `llm_service` and command interpretation paths.

## Proposed Solution

1. Capture per-call latency and token usage (when available) in structured logs.
2. Add lightweight aggregation counters for key paths (`/api/next`, `/api/action`).
3. Expose a debug metrics endpoint for local tuning.

## Scope Boundaries

- Keep existing API request/response payloads unchanged for `/api/next` and `/api/action`.
- Additive endpoint work only (`/api/debug/metrics`); no breaking route removals or renames.
- Keep metrics in-memory and local-process only (no persistence/migrations).
- No provider SDK changes or external telemetry dependencies in this item.

## Assumptions

- LLM providers may omit token usage; instrumentation must tolerate missing usage fields.
- Existing trace/request logging remains source of truth for per-request timing and should not be removed.
- Debug metrics can be exposed as best-effort operational telemetry for local tuning only.

## Files Affected

- `src/services/llm_service.py`
- `src/services/command_interpreter.py`
- `src/services/runtime_metrics.py` (new)
- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/api/game/metrics.py` (new)
- `src/api/game/__init__.py`
- `tests/service/test_llm_service.py`
- `tests/service/test_command_interpreter.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [x] Runtime LLM calls emit latency metrics in structured logs.
- [x] Token usage is captured when provider response includes it.
- [x] Metrics endpoint reports recent aggregates without exposing secrets.

## Validation Commands

- `python -m pytest -q tests/service/test_llm_service.py tests/service/test_command_interpreter.py tests/api/test_game_endpoints.py`
- `python -m pytest -q`
- `npm --prefix client run build`

## Risks and Rollback

- Risk: In-memory metrics can reset on process restart and may not reflect multi-process deployments.
- Risk: Additional instrumentation must stay non-blocking and never alter gameplay flow on failures.
- Rollback: Revert instrumentation and debug metrics endpoint commits for this item.
- Fast-disable path: Remove debug endpoint router include and keep existing request timing logs only.

## Closure Evidence (2026-03-03)

- Added structured per-call LLM metrics in `src/services/llm_service.py` and `src/services/command_interpreter.py` including duration, status, model, and token usage when present.
- Added in-memory aggregate counters in `src/services/runtime_metrics.py` and route wiring in `/api/next` and `/api/action`.
- Added debug endpoint `GET /api/debug/metrics` in `src/api/game/metrics.py` (dev-gated by `enable_dev_reset`) with router wiring in `src/api/game/__init__.py`.
- Added regression coverage in:
  - `tests/service/test_llm_service.py`
  - `tests/service/test_command_interpreter.py`
  - `tests/api/test_game_endpoints.py`

### Validation Results

- `python -m pytest -q tests/service/test_llm_service.py tests/service/test_command_interpreter.py tests/api/test_game_endpoints.py` -> `pass` (`98 passed, 9 warnings`)
- `python -m pytest -q` -> `pass` (`479 passed, 12 warnings`)
- `npm --prefix client run build` -> `pass` (`tsc --noEmit` + `vite build`)
