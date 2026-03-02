# Refactor spatial JSON handling with centralized helpers (behavior-preserving)

## Problem

Spatial/navigation code contains repeated JSON parsing patterns and mixed handling of dict-vs-string values. This increases fragility and makes behavior harder to audit.

## Proposed Solution

1. Introduce a small JSON utility module (for example `src/services/db_json.py`) with:
   - `loads_if_str(value)`
   - `dumps_if_dict(value)`
   - `safe_json_dict(value)`
2. Replace repetitive inline JSON parsing in `src/services/spatial_navigator.py` with the shared helpers.
3. Keep behavior unchanged and avoid broad data model changes in this phase.
4. Optionally migrate selected reads to ORM where it reduces ambiguity, without changing endpoint behavior.

## Files Affected

- `src/services/db_json.py` (new)
- `src/services/spatial_navigator.py`
- `src/api/game/spatial.py` (or `src/api/game.py` if router split not yet done)
- `tests/contract/test_spatial_navigation.py`
- `tests/contract/test_spatial_move.py`
- `tests/contract/test_spatial_map.py`
- `tests/contract/test_spatial_assign.py`
- `tests/integration/test_spatial_navigation_integration.py`

## Acceptance Criteria

- [ ] Spatial endpoints return unchanged payload shapes and semantics.
- [ ] Spatial code paths no longer duplicate ad-hoc JSON parsing logic.
- [ ] JSON helper behavior is unit-tested for dict/string/invalid input.
- [ ] `pytest -q` passes.

## Risks & Rollback

Risk is accidental type coercion changes affecting navigation decisions. Roll back by restoring original parsing code paths in `spatial_navigator.py` and removing helper usage.
