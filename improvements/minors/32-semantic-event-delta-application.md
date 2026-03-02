# Semantic World Event Delta Application

## Problem

`WorldEvent` objects in `src/models/__init__.py` have a `world_state_delta` field, but it is rarely used or applied. When a freeform action "changes state," the `command_interpreter.py` manually applies it to the player's variables, but it doesn't systematically update the *world's* persistent context (e.g., permanent changes to a location's status).

## Proposed Solution

1.  **Event Drip-Feed**: When a `WorldEvent` is recorded with a `delta`, apply those changes to the `AdvancedStateManager`'s environment or spatial nodes.
2.  **Long-Term Memory Persistence**: Ensure that events with `event_type="permanent_change"` are prioritized in the semantic context vector.
3.  **Semantic Triggers**: Create a hook in `world_memory.py` that can trigger a storylet *immediately* if a high-impact event delta occurs.

## Files Affected

- `src/services/world_memory.py`
- `src/services/state_manager.py`

## Acceptance Criteria

- [ ] A freeform action like "I blow up the bridge" sets a permanent `bridge_broken=True` state that persists across sessions and is reflected in future storylet selection.
- [ ] Event deltas are correctly merged into the global state history.
