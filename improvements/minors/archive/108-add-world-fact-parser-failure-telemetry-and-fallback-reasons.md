# Add world-fact parser failure telemetry and fallback reasons

## Problem
Fact extraction failures can currently be opaque, making it hard to distinguish model-output issues from parser/schema regressions.

## Proposed Solution
Add explicit parser/fallback telemetry and additive diagnostics for world-fact extraction.

- Emit counters for schema-parse success, schema-parse failure, fallback-invoked, and fallback-success.
- Attach bounded fallback reason fields to runtime diagnostics/artifacts.
- Add sampling-safe logs for malformed payload classes without leaking sensitive prompt content.

## Files Affected
- `src/services/world_memory.py`
- `src/services/runtime_metrics.py`
- `tests/service/test_world_memory.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria
- [ ] Parser/fallback telemetry counters are emitted for every extraction attempt.
- [ ] Fallback reasons are additive and bounded in diagnostics payloads.
- [ ] Logging remains safe and does not expose full prompt/response bodies.
- [ ] Tests cover success, parse-failure, and fallback paths.

## Validation Commands
- `pytest -q tests/service/test_world_memory.py tests/api/test_game_endpoints.py`
- `python scripts/dev.py quality-strict`
