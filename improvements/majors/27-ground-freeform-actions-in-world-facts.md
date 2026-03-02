# Ground freeform action resolution in world facts

## Problem

`src/services/command_interpreter.py` can return plausible narrative output, but it is not strongly constrained by durable world facts. It may introduce unsupported state keys, ignore prior events, or produce inconsistent deltas. This weakens trust in freeform play, which is central to the vision.

## Proposed Solution

1. Define a strict action-result contract in `src/models/schemas.py` (or dedicated models):
   - allowed delta shapes
   - typed operations (`set`, `increment`, `append_fact`)
   - optional confidence and rationale metadata
2. Before prompting the interpreter, retrieve relevant facts from world memory graph/projection and inject them into prompt context.
3. Validate and sanitize interpreter output:
   - reject unknown keys
   - coerce or drop invalid types
   - cap delta size and nested depth
4. Add contradiction handling:
   - if action conflicts with hard world facts, return in-world refusal or complication instead of silent overwrite
5. Persist action reasoning metadata to support debugging and future tuning.

## Files Affected

- `src/services/command_interpreter.py`
- `src/services/world_memory.py`
- `src/services/state_manager.py`
- `src/models/schemas.py`
- `src/api/game.py`
- `tests/service/test_command_interpreter.py`
- `tests/api/test_action_endpoint.py`

## Acceptance Criteria

- [ ] Interpreter receives relevant world facts for each action request.
- [ ] Invalid or unknown delta keys are blocked before state mutation.
- [ ] Contradictory actions result in coherent narrative refusal/complication.
- [ ] Action endpoint responses remain schema-valid under malformed model output.
- [ ] Tests cover hallucinated keys, type mismatches, and contradiction cases.

## Risks & Rollback

Over-constraining the interpreter can make freeform play feel rigid. Keep policy configurable, start with warnings in debug mode, and tighten enforcement iteratively. Roll back by relaxing validation and keeping only logging.
