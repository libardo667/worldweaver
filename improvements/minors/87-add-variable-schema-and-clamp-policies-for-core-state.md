# Add variable schema and clamp policies for core mutable state

## Problem

Core mutable variables lack a centralized schema for type/range/clamp policy.
Different mutation paths can introduce out-of-range or invalid values.

## Proposed Solution

Add a small canonical variable-policy map for high-impact fields:

1. Define per-field type/range/negative-allowance policy.
2. Apply policy during reducer commit prior to state persistence.
3. Emit validation warnings/metadata when values are clamped or dropped.

## Files Affected

- `src/services/state_manager.py`
- `src/services/rules/schema.py` (new or updated)
- `src/services/command_interpreter.py`
- `tests/service/test_state_manager.py`
- `tests/service/test_command_interpreter.py`

## Acceptance Criteria

- [ ] Core tracked variables enforce type/range policy on commit.
- [ ] Clamp/drop behavior is deterministic and test-covered.
- [ ] Validation outcomes are observable in metadata/logs for debugging.

