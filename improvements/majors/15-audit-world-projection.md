# Audit and Decide: WorldProjection Table

> ⏳ **REVISIT (parked 2026-06-08)** — not active, not dead. Wake-up trigger in [`improvements/REVISIT-LATER.md`](../REVISIT-LATER.md).

## Status
Blocked pending live observation. Do not execute until the investigation questions
below are answered.

## What WorldProjection Is

`WorldProjection` is an event-sourced key-value store distinct from both
`WorldFact` (semantic embeddings) and the now-removed SpatialNavigator.

When a `WorldEvent` fires with a `world_state_delta` payload, `record_event()`
calls `apply_event_to_projection()` (gated by `settings.enable_world_projection`),
which flattens the delta into rows:

```
path="environment.time_of_day"  value="evening"
path="variables.tension_level"  value=3
path="locations.market.open"    value=true
```

On every `get_state_manager()` call, `_sync_with_world_projection()` applies
these rows as overlays into the session's state manager. This is the
**shared world state sync** mechanism: if one agent's action shifts
`environment.weather`, every new or restored session picks up that value.

## Why It Was Flagged

It was incorrectly grouped with SpatialNavigator in the Major 09 cleanup notes.
The confusion arose from the name "projection" and the fact that the same file
(`world_memory.py`) handles both WorldFact embeddings and WorldProjection rows.

## Investigation Questions (answer before executing)

1. **Is the table populated in production?**
   Query: `SELECT COUNT(*) FROM world_projection;` on the live db.

2. **Are events actually writing `world_state_delta`?**
   Query: `SELECT COUNT(*) FROM world_events WHERE world_state_delta IS NOT NULL AND world_state_delta != 'null';`
   If zero — nothing is writing to WorldProjection and it's safe to drop.

3. **If populated: what paths exist?**
   `SELECT DISTINCT path FROM world_projection ORDER BY path;`
   This tells us whether `environment.*`, `variables.*`, or `locations.*` paths
   are actually being projected.

4. **If populated: is `apply_projection_overlay_to_state_manager` changing anything?**
   Add a temp debug log to `_sync_with_world_projection()` logging `applied`
   counts. If always `{variables: 0, environment: 0, locations: 0}` — the table
   exists but does nothing.

## Possible Outcomes

**Outcome A — table is empty / events never write world_state_delta:**
Safe to delete. Drop migration, remove model, remove functions from
`world_memory.py`, remove `_sync_with_world_projection` from `session_service.py`,
remove `/world/projection` endpoint and schema from `world.py`/`schemas.py`,
remove WorldProjection queries from `state.py`.

**Outcome B — table is populated but overlay applies nothing (all zeros):**
The delta format in events doesn't match what `_collect_projection_updates_from_delta`
expects. Investigate delta schema, then decide: fix the mismatch or drop the feature.

**Outcome C — table is populated and overlays are applying real values:**
WorldProjection is load-bearing shared world state. Before deleting, design a
replacement (options: fold into a dedicated WorldEnvironment table, use WorldNode
metadata, or promote the mechanism to a first-class feature with explicit writes).

## Files Affected (if dropped)

| File | Change |
|------|--------|
| `src/services/world_memory.py` | Remove `WorldProjection` import, `apply_event_to_projection`, `get_world_projection`, `rebuild_world_projection`, `apply_projection_overlay_to_state_manager`, `_collect_projection_updates_from_delta`, `PROJECTION_ROOT_*` constants |
| `src/services/session_service.py` | Remove `_sync_with_world_projection` and its two call sites |
| `src/api/game/world.py` | Remove `GET /world/projection` endpoint and `WorldProjectionResponse` import |
| `src/api/game/state.py` | Remove `WorldProjection` import and two `.query(WorldProjection)` delete blocks |
| `src/models/__init__.py` | Remove `WorldProjection` class |
| `src/models/schemas.py` | Remove `WorldProjectionEntryOut`, `WorldProjectionResponse` |
| `src/config.py` | Remove `enable_world_projection` field |
| Alembic | `DROP TABLE world_projection` migration |
