# Make world projection deterministic, explainable, and replayable from events

## Problem

World events are persisted, and `WorldProjection` exists, but projection is still
treated mostly as a convenience overlay (`_sync_with_world_projection` in
`src/services/session_service.py`) rather than the canonical computed truth.

Current operational gaps:

1. no single deterministic replay contract that proves projection rows are fully
   derivable from `world_events`,
2. limited explainability for "why this projected fact exists now", and
3. projection lifecycle is not explicitly gated against concurrent rebuilds.

## Proposed Solution

Implement an event-sourced projection contract:

1. Add deterministic projection replay/rebuild pipeline (full rebuild and
   scoped replay by prefix/session where applicable).
2. Add projection lineage metadata so each projected row can expose its source
   event chain in API/debug tooling.
3. Add conflict-resolution rules for competing updates (timestamp, confidence,
   permanence) as explicit code policy rather than implicit update order.
4. Add projection consistency checks used in tests and maintenance scripts.
5. Keep state-manager overlays read-only from projection, with commits only
   through event recording paths.

## Files Affected

- `src/services/world_memory.py`
- `src/services/session_service.py`
- `src/models/__init__.py`
- `src/models/schemas.py`
- `src/api/game/world.py`
- `scripts/rebuild_projection.py`
- `tests/service/test_world_projection.py`
- `tests/api/test_world_endpoints.py`

## Acceptance Criteria

- [ ] Running projection rebuild from `world_events` produces deterministic
      `WorldProjection` rows for the same event stream.
- [ ] Projection API payloads can surface lineage (`source_event_id` and
      explainable source metadata) for each projected entry.
- [ ] Concurrent projection rebuild attempts are serialized or rejected safely
      with no partial mixed state.
- [ ] Session state overlay reads projection data but does not mutate projection
      tables directly.
- [ ] A projection consistency test suite exists and passes.
- [ ] Existing world routes remain backward compatible.

## Risks & Rollback

Risk: projection policy changes may alter live world state interpretation and
break expected downstream behavior.

Rollback:

1. Preserve legacy projection update path behind a feature flag during rollout.
2. Keep rebuild commands idempotent and reversible.
3. If regressions appear, disable deterministic replay mode and restore prior
   projection application logic while root-causing policy mismatches.

