# Split author router and extract storylet ingest/postprocessing pipeline

## Problem

Author endpoints currently combine routing with ingestion, deduplication, spatial assignment, embedding, and auto-improvement orchestration. This creates deep endpoint functions and duplicated postprocessing flows.

## Proposed Solution

1. Split author routes into package modules:
   - `src/api/author/__init__.py`
   - `src/api/author/suggest.py`
   - `src/api/author/populate.py`
   - `src/api/author/generate.py`
   - `src/api/author/world.py`
2. Create `src/services/storylet_ingest.py` to centralize:
   - `deduplicate_and_insert(...)`
   - `assign_spatial_to_storylets(...)`
   - `postprocess_new_storylets(...)`
3. Ensure ingest service encapsulates embedding and auto-improvement triggers used by author routes.
4. Update author route modules to delegate ingest/postprocessing to service layer.
5. Keep public `/author/*` paths and response envelopes unchanged.

## Files Affected

- `src/api/author.py` (replaced by package layout)
- `src/api/author/__init__.py` (new)
- `src/api/author/suggest.py` (new)
- `src/api/author/populate.py` (new)
- `src/api/author/generate.py` (new)
- `src/api/author/world.py` (new)
- `src/services/storylet_ingest.py` (new)
- `main.py`
- `tests/api/test_author_validation.py`
- `tests/api/test_author_generate_world_confirmation.py`
- `tests/service/test_storylet_ingest.py` (new)

## Acceptance Criteria

- [ ] All `/author/*` endpoints remain on the same URLs with same payload shapes.
- [ ] Ingest/deduplication/postprocessing logic lives in one service module.
- [ ] Author route modules are thin and endpoint-focused.
- [ ] `pytest -q` passes.

## Risks & Rollback

Risk is subtle semantic drift in author postprocessing flow. Roll back by restoring consolidated logic in the original author router and removing `storylet_ingest.py`.
