# Introduce an authoritative event reducer and rulebook for all world-state mutations

## Problem

State mutations currently enter through multiple paths with inconsistent policy
enforcement:

- `/api/next` applies inbound `payload.vars` directly (`src/api/game/story.py`).
- `/api/action` applies interpreter deltas through world-memory pathways
  (`src/api/game/action.py`, `src/services/command_interpreter.py`).
- Choice `set` payloads can be pre-applied on the client
  (`applyLocalSet` in `client/src/App.tsx`) before server roundtrip.

This allows alias drift and inconsistent semantics (for example `danger` vs
`environment.danger_level`) and weakens deterministic replay/debuggability.

## Proposed Solution

Create a single backend reducer/rulebook layer that owns all authoritative world
state transitions:

1. Add a reducer entrypoint (for example `reduce_event(...)`) that accepts
   normalized event intents:
   - `choice_selected`,
   - `freeform_action_committed`,
   - `system_tick`.
2. Add a rulebook/policy module that enforces:
   - canonical key mapping/aliasing,
   - allowed mutation paths and operations,
   - type/range validation and clamping,
   - deterministic side-effect rules.
3. Route `/api/next` and `/api/action` state writes through this reducer before
   commit/event recording.
4. Emit reducer receipts with:
   - proposed vs applied deltas,
   - dropped/rejected ops,
   - reasons for rejections.
5. Keep public payload shapes backward compatible while extending debug metadata.

## Files Affected

- `src/services/state_manager.py`
- `src/services/world_memory.py`
- `src/services/command_interpreter.py`
- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/models/schemas.py`
- `src/services/rules/reducer.py` (new)
- `src/services/rules/schema.py` (new)
- `tests/service/test_state_manager.py`
- `tests/service/test_command_interpreter.py`
- `tests/api/test_game_endpoints.py`
- `tests/api/test_action_endpoint.py`

## Acceptance Criteria

- [x] All persistent world-state mutations flow through one reducer entrypoint.
- [x] Reducer enforces canonical aliases and mutation policy consistently across
      `/api/next` and `/api/action`.
- [x] Rejected or transformed mutations are observable in reducer receipts.
- [x] Alias drift regressions (`danger` vs `environment.danger_level`) are
      covered by tests.
- [x] Existing route/path/payload contracts remain backward compatible.
- [x] `python -m pytest -q tests/api/test_game_endpoints.py
      tests/api/test_action_endpoint.py` passes.

## Risks & Rollback

Risk: centralizing mutation policy can surface latent assumptions and cause
behavior changes in existing stories.

Rollback:

1. Gate reducer enforcement behind a config flag while integrating incrementally.
2. Keep legacy mutation path available for emergency fallback.
3. If regressions appear, disable strict reducer mode and re-enable path-by-path
   behavior while addressing policy gaps with tests.
