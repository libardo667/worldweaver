# Inject relevant world facts into freeform action prompts

## Problem

`src/services/command_interpreter.py` uses recent event summaries but does not retrieve semantically relevant world facts for each action. This can cause avoidable contradiction with established history.

## Proposed Solution

1. Query `world_memory.query_world_facts()` for the action text before prompt assembly.
2. Add top fact summaries to the action prompt context.
3. Cap fact count and token usage to avoid prompt bloat.

## Files Affected

- `src/services/command_interpreter.py`
- `src/services/world_memory.py`
- `tests/service/test_command_interpreter.py`

## Acceptance Criteria

- [ ] Action prompts include retrieved world fact snippets when available.
- [ ] Retrieved facts are session-scoped when `session_id` is present.
- [ ] Prompt size remains bounded by configured limits.
