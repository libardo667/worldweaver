# Add an event-sourced world state projection

## Problem

World state is split between session-scoped `SessionVars` and event logs in `WorldEvent`. There is no canonical, queryable world projection that says "what is currently true" independent of one player session. This blocks consistent NPC memory, environment continuity, and cross-turn coherence.

## Proposed Solution

1. Add a persistent projection model (for example `WorldProjection`) keyed by fact path:
   - `path` (string key such as `locations.bridge.status`)
   - `value` (JSON value)
   - `source_event_id`
   - `updated_at`
2. Implement a reducer in `src/services/world_memory.py` that applies each event delta to projection state:
   - deterministic merge rules
   - conflict resolution by timestamp/confidence
   - support for tombstones/removals
3. Update `AdvancedStateManager` composition in `src/api/game.py`:
   - session state overlays world projection for player-specific keys only
   - world keys come from projection by default
4. Add backfill command to rebuild projection from existing `WorldEvent` history.
5. Add diagnostic endpoint to inspect current projection and source lineage.

## Files Affected

- `src/models/__init__.py`
- `alembic/versions/*` (new migration)
- `src/services/world_memory.py`
- `src/services/state_manager.py`
- `src/api/game.py`
- `src/models/schemas.py`
- `tests/service/test_world_memory.py`
- `tests/integration/test_session_persistence.py`

## Acceptance Criteria

- [ ] World projection reflects permanent changes after freeform actions and storylet events.
- [ ] Projection survives server restarts and new sessions.
- [ ] Session state no longer silently diverges from global world truth for shared keys.
- [ ] A full projection rebuild from event history produces deterministic output.
- [ ] Projection endpoint shows key/value plus source event metadata.

## Risks & Rollback

Bad merge semantics can overwrite valid world facts. Keep reducer pure and testable, version projection schema, and support rebuilding from events at any time. Roll back by switching reads back to session-only state while preserving projection data.
