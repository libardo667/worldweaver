# PRUNING Lane 3 Evidence

Date: 2026-03-03
Lane: 3 (Legacy Ingest/Runtime Pruning)

## Files Changed
- `src/services/story_smoother.py`
- `src/services/auto_improvement.py`
- `src/services/storylet_ingest.py`
- `src/api/game/state.py`
- `src/api/game/__init__.py`
- `src/api/author/__init__.py`
- `src/config.py`
- `tests/service/test_decomposed_functions.py`
- `tests/api/test_game_endpoints.py`

## What Changed and Why
- Demoted runtime smoothing/spatial mutation path:
  - Added `WW_ENABLE_STORY_SMOOTHING` (`settings.enable_story_smoothing`, default `False`).
  - `run_auto_improvements()` now forwards smoothing as opt-in from config.
  - `auto_improve_storylets()` now skips smoothing when the flag is off.
  - `StorySmoother.smooth_story()` now takes `apply_spatial_fixes` and only runs spatial auto-fixer when explicitly requested.
- Deleted refactor-transition compatibility layers:
  - Removed `save_storylets_with_postprocessing()` alias from `storylet_ingest`.
  - Removed author package compatibility re-exports from `src/api/author/__init__.py`.
  - Pruned `src/api/game/__init__.py` compatibility re-exports to a minimal surface used by shared fixtures/tests (`_state_managers`, `_spatial_navigators`, `cleanup_old_sessions`).
  - Updated decomposition test import to source ingest helpers directly from `src.services.storylet_ingest`.
- Isolated legacy reset seeding path:
  - `/api/reset-session` legacy reseed now requires both:
    - `include_legacy_seed=true` request parameter
    - `settings.enable_legacy_test_seeds == True`
  - Response contract keys unchanged (`success`, `message`, `deleted`, `storylets_seeded`, `legacy_seed_mode`).
  - Updated API test to explicitly enable legacy seed setting for optional legacy mode assertion.

## Validations Run and Results
Required lane validation command:

- Command:
  - `python -m pytest -q tests/service/test_storylet_ingest.py tests/service/test_decomposed_functions.py tests/service/test_seed_data.py tests/api/test_game_endpoints.py tests/api/test_author_generate_world_confirmation.py tests/api/test_route_smoke.py`
- Result:
  - `79 passed, 9 warnings in 5.40s`
- Status: PASS

## Unresolved Risks
- `src/api/game/__init__.py` and `src/api/author/__init__.py` removed transition-era re-exports; any external imports relying on removed symbols (outside current test coverage) may break.
- Story smoothing is now opt-in. Environments expecting previous automatic smoothing behavior must set `WW_ENABLE_STORY_SMOOTHING=1`.
- `/api/reset-session?include_legacy_seed=true` no longer seeds unless `WW_ENABLE_LEGACY_TEST_SEEDS=1`; operators may need configuration updates for legacy test workflows.

## Handoff Notes for Integration
- Contract C4 retained: reset payload shape unchanged; only legacy seed activation semantics tightened.
- Contract C5 retained: `postprocess_new_storylets()` response envelope unchanged.
- Lane 1 consumer impact: no field-level payload changes for reset/session endpoints.
- Suggested integration checks after merge:
  1. Run full suite (`python -m pytest -q`) to detect any downstream imports of removed compatibility aliases.
  2. Confirm deployment env expectations for `WW_ENABLE_STORY_SMOOTHING` and `WW_ENABLE_LEGACY_TEST_SEEDS`.
  3. If needed for rollback behavior, temporarily restore prior behavior via env flags (no schema changes required).
