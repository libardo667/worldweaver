# Add a storylet effects contract and server-side application on fire/choice commit

## Problem

Storylets currently rely on `requires`/`choices` plus narration, but there is no
first-class `effects` contract that deterministically applies world/state changes
when a storylet fires or a choice commits.

## Proposed Solution

Add optional structured storylet effect operations:

1. Extend storylet schema with optional `effects` list (typed operations).
2. Apply effects through the server reducer when a storylet fires and/or when a
   selected choice commits.
3. Record applied effects in event metadata for replay/debug.

## Files Affected

- `src/models/__init__.py`
- `src/models/schemas.py`
- `src/services/storylet_selector.py`
- `src/api/game/story.py`
- `src/services/world_memory.py`
- `tests/service/test_storylet_selector.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [ ] Storylets can declare structured effects independent of narration text.
- [ ] Effects are validated and applied server-side via the reducer path.
- [ ] Effect application is recorded and replayable via world event history.
- [ ] Existing storylets without effects continue to work unchanged.

