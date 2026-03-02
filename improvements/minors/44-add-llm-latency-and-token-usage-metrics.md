# Add LLM latency and token usage metrics for runtime calls

## Problem

As runtime adaptation and synthesis increase, there is limited visibility into latency and token cost for `llm_service` and command interpretation paths.

## Proposed Solution

1. Capture per-call latency and token usage (when available) in structured logs.
2. Add lightweight aggregation counters for key paths (`/api/next`, `/api/action`).
3. Expose a debug metrics endpoint for local tuning.

## Files Affected

- `src/services/llm_service.py`
- `src/services/command_interpreter.py`
- `src/api/game.py`
- `tests/diagnostic/test_llm_config.py` (or new metrics test)

## Acceptance Criteria

- [ ] Runtime LLM calls emit latency metrics in structured logs.
- [ ] Token usage is captured when provider response includes it.
- [ ] Metrics endpoint reports recent aggregates without exposing secrets.
