# Batch B Runtime Services Slice 3

Date: `2026-03-06`
Status: `completed`

## Scope
- Remove remaining direct runtime-service entrypoints into legacy improvers.
- Centralize auto-improvement flag gating and skip-reason telemetry through one adapter path.

## Changes
1. Centralized runtime-service improvement orchestration:
- `src/services/game_logic.py`
  - `ensure_storylets(...)` now routes improvement execution through `run_auto_improvements(...)`.
  - `auto_populate_storylets(...)` now routes improvement execution through `run_auto_improvements(...)`.
  - removed direct `auto_improve_storylets(...)` callsites from runtime generation entrypoints.

2. Preserved/clarified skip telemetry in adapter:
- `src/services/storylet_ingest.py`
  - explicit skip logs in `run_auto_improvements(...)`:
    - `empty_trigger`
    - `both_flags_disabled`
    - `trigger_not_selected`

3. Added regression tests for adapter routing:
- `tests/service/test_decomposed_functions.py`
  - `test_routes_auto_improvement_through_ingest_adapter` under `TestEnsureStorylets`
  - `test_routes_auto_improvement_through_ingest_adapter` under `TestAutoPopulateStorylets`

## Guardrail Verification
Commands:
- `ruff check src/services/game_logic.py src/services/storylet_ingest.py tests/service/test_decomposed_functions.py`
- `pytest -q tests/service/test_decomposed_functions.py tests/service/test_storylet_ingest.py tests/integration/test_author_pipeline_transactions.py`
- `python scripts/dev.py quality-strict`

Results:
- Lint: pass
- Targeted tests: `20 passed`
- Full strict gate: pass (`583 passed`; warning budget unchanged)
- Note: one transient failure was observed on first strict run in `tests/service/test_storylet_selector.py::test_sparse_context_triggers_runtime_synthesis`; isolated rerun passed, and full strict rerun passed.

## Batch B Impact
- Runtime-service auto-improvement flow is now funneled through one adapter (`run_auto_improvements`) instead of multiple direct legacy improver callsites.
- This lowers drift risk and creates a clean seam for optional quarantine/removal work in a follow-up slice.
