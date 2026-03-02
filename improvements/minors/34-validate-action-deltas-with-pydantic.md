# Validate freeform action deltas with a strict Pydantic contract

## Problem

`/api/action` currently trusts LLM-produced `state_changes` as plain dict data. Invalid shapes or unexpected keys can leak into state and create hard-to-debug inconsistencies.

## Proposed Solution

1. Add an `ActionDelta` schema in `src/models/schemas.py` with typed fields and validators.
2. Validate parsed interpreter output before applying deltas.
3. Return a safe fallback response when validation fails.

## Files Affected

- `src/models/schemas.py`
- `src/services/command_interpreter.py`
- `src/api/game.py`
- `tests/service/test_command_interpreter.py`

## Acceptance Criteria

- [ ] Invalid delta payloads are rejected before state mutation.
- [ ] Valid deltas pass through unchanged.
- [ ] Action endpoint remains stable when interpreter output is malformed.
