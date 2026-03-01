# Validate types in requirement numeric comparisons

## Problem

`src/services/game_logic.py` `meets_requirements()` (lines 22-51) performs
numeric comparisons (`gte`, `lte`, etc.) on whatever value `vars.get(key)`
returns. If the value is a string or a list instead of a number, Python
raises a `TypeError` and the entire `/api/next` request crashes with a 500
error. There is no type guard.

## Proposed Fix

Before each comparison operator block, check that `have` is an `int` or
`float`. If it is not, treat the requirement as unmet (return `False`)
and log a warning. This keeps the function pure (no exceptions) and
degrades gracefully on bad data.

## Files Affected

- `src/services/game_logic.py`

## Acceptance Criteria

- [ ] `meets_requirements({"score": "abc"}, {"score": {"gte": 5}})` returns
      `False` instead of raising `TypeError`
- [ ] A warning is logged when a non-numeric value is compared
