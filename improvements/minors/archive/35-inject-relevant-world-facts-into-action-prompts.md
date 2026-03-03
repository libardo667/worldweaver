# Ground freeform action prompts with world facts and strict delta validation

## Problem

`src/services/command_interpreter.py` uses recent event summaries but does not consistently retrieve semantically relevant world facts for each action. In addition, `/api/action` can accept loosely structured `state_changes` payloads from model output, allowing malformed deltas to leak into state.

## Proposed Solution

1. Query `world_memory.query_world_facts()` (or graph fact equivalent) for the action text before prompt assembly.
2. Add top fact summaries to the action prompt context.
3. Add an `ActionDelta` Pydantic schema (or equivalent strict validator) in `src/models/schemas.py`.
4. Validate parsed interpreter output before applying state changes.
5. Return a safe fallback response when delta validation fails.
6. Cap fact count and token usage to avoid prompt bloat.

## Files Affected

- `src/services/command_interpreter.py`
- `src/services/world_memory.py`
- `src/models/schemas.py`
- `src/api/game.py`
- `tests/service/test_command_interpreter.py`
- `tests/api/test_action_endpoint.py`

## Acceptance Criteria

- [x] Action prompts include retrieved world fact snippets when available.
- [x] Retrieved facts are session-scoped when `session_id` is present.
- [x] Invalid delta payloads are rejected before state mutation.
- [x] Valid deltas pass through unchanged.
- [x] Action endpoint remains stable when interpreter output is malformed.
- [x] Prompt size remains bounded by configured limits.
