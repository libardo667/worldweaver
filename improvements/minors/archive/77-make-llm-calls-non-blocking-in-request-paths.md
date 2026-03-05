# Make LLM calls non-blocking in request paths

## Disposition

Completed and archived on March 4, 2026.

## Problem

Current request paths call synchronous LLM clients (`client.chat.completions.create`)
inside API execution flows (`src/services/llm_client.py`,
`src/services/llm_service.py`, `src/services/command_interpreter.py`). Under
load, this can increase head-of-line blocking and latency jitter.

## Proposed Solution

Isolate LLM calls from blocking request execution:

1. Introduce async-compatible LLM call wrappers (async client or thread-offload).
2. Update high-latency routes (`/api/next`, `/api/action`, `/api/action/stream`)
   to use non-blocking wrappers.
3. Preserve existing timeout, retry, and metrics behavior.
4. Add regression tests for timeout handling and route responsiveness.

## Files Affected

- `src/services/llm_client.py`
- `src/services/llm_service.py`
- `src/services/command_interpreter.py`
- `src/api/game/story.py`
- `src/api/game/action.py`
- `tests/api/test_action_endpoint.py`
- `tests/api/test_story_endpoint.py`

## Acceptance Criteria

- [x] LLM request execution is isolated from blocking the main event loop.
- [x] Existing timeout and retry semantics remain intact.
- [x] Route timing metrics continue to emit with unchanged field names.
- [x] Endpoint contract tests for `/api/action` and `/api/next` pass.

## Execution Evidence (March 4, 2026)

- Added async thread-offload wrapper `run_inference_thread()` in
  `src/services/llm_client.py`.
- Converted request handlers to async and routed heavy work through offload
  wrapper in:
  - `src/api/game/story.py` (`/api/next`)
  - `src/api/game/action.py` (`/api/action`, `/api/action/stream`)
- Added async-compatible wrappers in:
  - `src/services/llm_service.py`
  - `src/services/command_interpreter.py`
- Added API regression tests:
  - `tests/api/test_story_endpoint.py`
  - `tests/api/test_action_endpoint.py` (non-blocking wrapper coverage)
- Validation:
  - `python -m pytest -q` -> `528 passed`
  - `python scripts/dev.py gate3` -> pass
  - `npm --prefix client run build` -> pass
