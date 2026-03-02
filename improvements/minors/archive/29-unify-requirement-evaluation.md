# Unify the three requirement-evaluation implementations

## Problem

There are three separate implementations of requirement evaluation:

1. `game_logic.meets_requirements` (lines ~25-59) — supports gte, lte,
   gt, lt, eq, ne operators
2. `state_manager.AdvancedStateManager.evaluate_condition` (lines ~388-473)
   — supports the same plus magic location strings
3. `spatial_navigator.SpatialNavigator._check_requirements` (lines ~478-504)
   — a third copy that does NOT support eq/ne operators

These can diverge silently. A storylet that passes requirements in one
code path may fail in another, causing inconsistent behaviour depending
on which path the request takes.

## Proposed Fix

Extract a single `evaluate_requirements(requires: dict, vars: dict) -> bool`
function into a shared location (e.g., `src/services/requirements.py` or
as a module-level function in `game_logic.py`). Have all three call sites
delegate to it. The unified version should support all operators from
all three implementations.

## Files Affected

- `src/services/game_logic.py` — extract and delegate
- `src/services/state_manager.py` — delegate to shared function
- `src/services/spatial_navigator.py` — delegate to shared function

## Acceptance Criteria

- [ ] Only one implementation of requirement evaluation exists
- [ ] All three former call sites use the shared implementation
- [ ] The shared version supports all operators (gte, lte, gt, lt, eq, ne)
- [ ] Existing tests still pass
