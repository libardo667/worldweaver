# PRUNING Lane 2 Evidence (2026-03-03)

## Files Changed
- `src/services/spatial_navigator.py`
- `tests/contract/test_spatial_navigation.py`
- `tests/contract/test_spatial_move.py`
- `tests/service/test_spatial_navigator.py`

## What Changed
- Hardened spatial navigation direction affordance to return only traversable directions (`accessible == true`) in `directions`.
- Added a contract-compatible `score` field in semantic lead payloads (mirrors existing `blended_score`) without removing existing fields.
- Merged legacy choice parsing (`set` vs `set_vars`) behind one helper path in spatial navigator to reduce repeated compatibility branches.
- Added/updated tests to lock:
  - spatial navigation envelope required keys and lead contract keys (`direction`, `title`, `score`),
  - blocked movement semantics (`403` with `detail="Cannot move in that direction"`),
  - service-level guarantee that blocked adjacent targets are excluded from `directions`.

## Validations Run
Required Lane 2 command:
- `python -m pytest -q tests/contract/test_spatial_navigation.py tests/contract/test_spatial_move.py tests/contract/test_spatial_map.py tests/service/test_spatial_navigator.py tests/api/test_prefetch_endpoints.py tests/service/test_prefetch_service.py tests/integration/test_spatial_navigation_integration.py`

Result:
- `16 passed, 3 warnings`.
- Warnings are existing unrelated Pydantic protected-namespace warnings for `model_id` fields.

## Unresolved Risks
- Full-repo validation (`python -m pytest -q`) was not run in this lane pass, so cross-area regressions outside lane-owned suites are unverified.
- Navigation still computes directional adjacency before accessibility filtering; behavior is now contract-safe but may still include non-traversable targets in `available_directions` metadata by design.
- Existing warning debt (Pydantic `model_id` protected namespace) remains.

## Handoff Notes For Integration
- Lane 1 can rely on `GET /api/spatial/navigation/{session_id}` `directions` as traversable-only (requirements already enforced).
- C1 lead payload now includes explicit `score` while preserving prior fields (`semantic_score`, `blended_score`) for compatibility.
- C2 blocked-move error contract is explicitly locked by test (`403` + exact detail text).
- No prefetch endpoint shape changes were made; C3 remains stable.
