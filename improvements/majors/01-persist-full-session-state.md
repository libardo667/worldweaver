# Persist full session state to database

## Problem

Only `state_manager.variables` is written to the `session_vars` table
(`src/api/game.py` line 139). The `AdvancedStateManager` also tracks
inventory (`items` dict), relationships (`relationships` dict), and
environment (`environmental_state`), but none of these survive a server
restart. A player who picks up a sword, befriends an NPC, and triggers a
weather change loses all of it the moment uvicorn recycles.

## Proposed Solution

1. Add an `export_state()` / `import_state()` round-trip that serialises the
   full `AdvancedStateManager` into a single JSON blob. The state manager
   already has these methods (`state_manager.py` lines 590-605 for export),
   but they are never called from the API layer.
2. Replace the current save logic in `game.py` (`_save_session`) so it
   calls `export_state()` and stores the result in `session_vars.vars`.
3. On session load (`get_state_manager`), call `import_state()` with the
   stored blob instead of only copying `legacy_vars`.
4. Add a schema version key (`"_v": 2`) to the exported JSON so old
   sessions can be detected and migrated transparently.

## Files Affected

- `src/api/game.py` — save/load logic
- `src/services/state_manager.py` — add version key to export, harden
  import against missing fields
- `src/models/__init__.py` — no schema change needed; `vars` column is
  already JSON

## Acceptance Criteria

- [ ] Inventory items survive a full server restart
- [ ] NPC relationships survive a full server restart
- [ ] Environmental state (weather, time-of-day, danger) survives restart
- [ ] Legacy v1 sessions (plain variable dicts) still load correctly
- [ ] New sessions are saved with `"_v": 2` marker
- [ ] Integration test covers save → restart → load cycle

## Risks & Rollback

The `session_vars.vars` column is untyped JSON, so the larger payload fits
without migration. Rollback: revert the two-file change; old sessions
remain readable because the import path already falls back to treating the
blob as flat variables.
