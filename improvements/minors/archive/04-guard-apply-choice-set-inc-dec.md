# Guard inc/dec operations in apply_choice_set against non-numeric values

## Problem

`src/services/game_logic.py` `apply_choice_set()` (lines 122-137) uses
`int()` to convert increment/decrement values without a try/except. If a
storylet's choice `set` contains `{"gold": {"inc": "lots"}}`, the call
crashes with `ValueError`. The same applies to the current variable value
— if `vars["gold"]` is `None` or a string, the `+= int(...)` line fails.

## Proposed Fix

Wrap the `int()` conversions in a try/except `(TypeError, ValueError)`.
On failure, skip the operation and log a warning with the variable name
and the offending value. Default the current value to `0` when it is
missing or non-numeric.

## Files Affected

- `src/services/game_logic.py`

## Acceptance Criteria

- [ ] `apply_choice_set({"gold": "oops"}, {"gold": {"inc": 5}})` does not
      raise; `gold` becomes `5`
- [ ] `apply_choice_set({}, {"gold": {"inc": "bad"}})` does not raise;
      `gold` is unchanged
