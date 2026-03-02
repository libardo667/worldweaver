# Add WorldEvent model and persistent world memory

## Problem

The vision's key differentiator is: "events become permanent world facts."
Currently there is no way to record that something happened in the world
independently of a player's session variables. When a storylet fires, it
updates the player's `session_vars` but nothing is stored at the *world*
level. NPCs can't remember across sessions. The bridge you burned is only
burned in your session's key-value store.

There is no `WorldEvent` table, no event log, and no way to query "what
has happened in this world so far."

## Proposed Solution

1. **Add `WorldEvent` SQLAlchemy model** with:
   - `id` (int, PK)
   - `session_id` (str, FK to session_vars — who caused it)
   - `storylet_id` (int, FK to storylets — which storylet fired)
   - `event_type` (str — "storylet_fired", "choice_made", "freeform_action")
   - `summary` (str — human-readable description of what happened)
   - `embedding` (JSON, nullable — vector embedding of the event for
     semantic queries)
   - `world_state_delta` (JSON — what changed: `{"bridge_status": "burned"}`)
   - `created_at` (datetime)

2. **Add `WorldMemory` service** (`src/services/world_memory.py`):
   - `record_event(db, session_id, storylet_id, event_type, summary, delta)`
   - `get_world_history(db, limit=50) -> list[WorldEvent]`
   - `get_world_context_vector(db) -> list[float]` — aggregate embedding
     of recent world events (used by the semantic selection engine to
     weight storylets based on world state, not just player state)
   - `query_world_facts(db, query: str) -> list[WorldEvent]` — semantic
     search over world history

3. **Hook into game flow** — when `pick_storylet` returns a storylet and
   the player makes a choice, record a `WorldEvent`.

4. **Add API endpoints**:
   - `GET /api/world/history` — recent world events
   - `GET /api/world/facts?query=bridge` — semantic query

## Files Affected

- `src/models/__init__.py` — new `WorldEvent` model
- `src/services/world_memory.py` — new service
- `src/api/game.py` — record events on storylet fire / choice
- `src/api/game.py` — new world history/facts endpoints
- `src/models/schemas.py` — new response models
- `tests/service/test_world_memory.py` — new tests

## Acceptance Criteria

- [ ] `WorldEvent` table is created with all specified columns
- [ ] Firing a storylet records a WorldEvent with a summary
- [ ] Making a choice records a WorldEvent with the choice details
- [ ] `get_world_history` returns events in reverse chronological order
- [ ] `get_world_context_vector` returns an aggregate embedding
- [ ] `GET /api/world/history` returns the event log
- [ ] Events persist across server restarts (they're in the DB)
- [ ] Tests cover recording, retrieval, and aggregation

## Risks & Rollback

New table and service — purely additive. If event recording causes
performance issues, it can be made async or batched. Rollback: drop the
table, remove the service, remove the hooks.
