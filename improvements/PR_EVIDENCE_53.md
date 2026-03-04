# PR Evidence: 53-make-world-projection-deterministic-explainable-and-replayable

## What Changed
- Validated that `WorldProjection` models in `src/models/__init__.py` already support deterministic rebuilds with `source_event_id` and `metadata_json`.
- Verified that API schema models correctly expose this lineage metadata in `src/api/game/world.py`.
- Wrote maintenance script `scripts/rebuild_projection.py` to allow operator-triggered deterministic rebuilds of the graph table.
- Added comprehensive determinism and lineage tests in `tests/service/test_world_projection.py`.
- Confirmed that `session_service.py` is safely isolated and `_sync_with_world_projection` correctly overlays the projection without directly mutating the database tables out of band.

## Why it Changed
- To fulfill the foundational requirement for rigorous fact grounding (Issue #54) by ensuring the active world simulation represents a strict, deterministic fold over the log of immutable `world_events`. 

## Verification Performed
- `python scripts/rebuild_projection.py` ran successfully on local SQLite database, verifying safe operation on existing payload shapes.
- `python -m pytest -q tests/service/test_world_projection.py` passed with 100% success mapping lineage event IDs and tracking deterministic regeneration.
- No changes made to API endpoints to ensure contract backward compatibility.

## Known Risks & Next Steps
- **Risks:** High volume rebuilds on massive session lengths could lock SQLite file for ~seconds, causing query timeout for concurrent API reads. Can be mitigated if needed with batch commits.
- **Next Steps:** Proceed with Phase 2 (Issue #52) to establish the normalized Canonical Entity Resolution in the Graph.
