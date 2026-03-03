# Normalize world event taxonomy and delta key conventions

## Problem

Event typing is currently flexible (`storylet_fired`, `freeform_action`, inferred permanent changes), which makes downstream analytics and reducers harder to maintain. Delta keys also vary in shape across producers.

## Proposed Solution

1. Define canonical event type constants in `src/services/world_memory.py`.
2. Add a normalization layer for inbound event types and delta keys.
3. Emit warnings for unknown event types in debug logs.

## Files Affected

- `src/services/world_memory.py`
- `src/api/game.py`
- `tests/service/test_world_memory.py`

## Acceptance Criteria

- [x] All recorded events are normalized to approved event type values.
- [x] Unknown event types are logged and mapped to a safe fallback type.
- [x] Tests cover normalization for existing event producers.
