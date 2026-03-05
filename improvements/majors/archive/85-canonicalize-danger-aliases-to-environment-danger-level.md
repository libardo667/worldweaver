# Canonicalize danger aliases to `environment.danger_level`

## Problem

Runtime state currently allows both `danger` and `danger_level` style usage
across payloads/prompts, creating ambiguity and potential divergence in derived
context.

## Proposed Solution

Add canonical alias policy so danger semantics have one truth path:

1. Normalize inbound `danger` writes to `environment.danger_level`.
2. Prevent persistent direct writes to ambiguous flat `danger` unless explicitly
   configured as derived mirror output.
3. Update API examples and client display mapping to use canonical field names.

## Files Affected

- `src/services/state_manager.py`
- `src/services/world_memory.py`
- `src/models/schemas.py`
- `src/api/game/story.py`
- `client/src/App.tsx`
- `tests/api/test_game_endpoints.py`
- `tests/service/test_state_manager.py`

## Acceptance Criteria

- [ ] Incoming danger alias variants normalize to one canonical stored field.
- [ ] Contextual variable outputs no longer drift between `danger` and
      `danger_level`.
- [ ] Existing tests and API contracts remain backward compatible.

