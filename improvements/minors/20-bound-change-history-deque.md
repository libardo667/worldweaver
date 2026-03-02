# Bound change_history with a maxlen deque

## Problem

`src/services/state_manager.py` appends to `self.change_history` on every
call to `set_variable`, `add_item`, `update_relationship`, etc. This list
grows without bound for the lifetime of the session (up to 24 hours before
cleanup). Each `StateChange` object stores a copy of the pre-change value.
Long-lived or active sessions can accumulate thousands of entries, wasting
memory. The history is explicitly excluded from persistence (`export_state`),
so unbounded growth serves no purpose.

## Proposed Fix

Replace `self.change_history: list = []` with
`self.change_history: deque = deque(maxlen=200)` (import `deque` from
`collections`). 200 entries is enough for meaningful rollback while
bounding memory.

## Files Affected

- `src/services/state_manager.py`

## Acceptance Criteria

- [ ] `change_history` is a `deque` with `maxlen=200`
- [ ] Old entries are silently dropped when the deque is full
- [ ] Existing rollback functionality still works within the 200-entry window
