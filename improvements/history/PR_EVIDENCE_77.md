# PR Evidence: Minor 77 - Non-Blocking LLM Calls in Request Paths

## Item

`improvements/minors/archive/77-make-llm-calls-non-blocking-in-request-paths.md`

## Scope

Implemented thread-offloaded, async-compatible inference execution for high-latency
API request paths while preserving existing route contracts and metrics shape.

## What Changed

| File | Change |
|------|--------|
| `src/services/llm_client.py` | Added `run_inference_thread()` async wrapper (`anyio.to_thread.run_sync`) for blocking inference work. |
| `src/services/llm_service.py` | Added async-compatible wrappers (`adapt_storylet_to_context_non_blocking`, `generate_next_beat_non_blocking`). |
| `src/services/command_interpreter.py` | Added async-compatible wrappers for staged and legacy action interpretation/narration paths. |
| `src/api/game/story.py` | Converted `/api/next` handler to `async` and offloaded heavy turn resolution + prefetch scheduling via `run_inference_thread()`. |
| `src/api/game/action.py` | Converted `/api/action` and `/api/action/stream` handlers to `async` and offloaded heavy resolution/prefetch via `run_inference_thread()`. |
| `tests/api/test_story_endpoint.py` | Added regression coverage for `/api/next` non-blocking wrapper usage and timeout surfacing behavior. |
| `tests/api/test_action_endpoint.py` | Added regression coverage for `/api/action` and `/api/action/stream` non-blocking wrapper usage. |
| `improvements/minors/archive/77-make-llm-calls-non-blocking-in-request-paths.md` | Marked acceptance complete and archived with execution evidence. |
| `improvements/ROADMAP.md` | Marked minor 77 complete and updated execution-order notes. |

## Why This Matters

Blocking LLM calls in request paths can starve async request execution under load
and increase latency jitter. Thread-offloading keeps event-loop request handling
responsive while preserving existing behavior contracts. This improves reliability
for interactive endpoints where perceived responsiveness is product-critical.

## Quality Gate Evidence

### Gate 1: Contract Integrity

- No route path changes.
- No response payload shape changes for `/api/next`, `/api/action`, `/api/action/stream`.

### Gate 2: Correctness

- `python -m pytest -q` -> `528 passed, 14 warnings`

### Gate 3: Build and Static Health

- `python -m ruff check src/api src/services src/models main.py` -> pass
- `python -m black --check src/api src/services src/models main.py` -> pass
- `python scripts/dev.py lint-all` -> pass
- `python scripts/dev.py gate3` -> pass
- `npm --prefix client run build` -> pass

### Gate 5: Operational Safety

- Rollback path: revert this PR to restore prior synchronous route execution.
- No schema migration or persistent state format change introduced.

## Residual Risk

- Thread-offload adds worker-thread scheduling overhead; behavior is stable but
  throughput tuning may still be needed under sustained production-level load.
