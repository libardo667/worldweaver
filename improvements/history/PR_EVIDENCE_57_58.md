# PR Evidence

## Change Summary

- Item ID(s): `57`, `58`
- PR Scope: Implemented session-level in-process synchronization and explicit session consistency modes for runtime state handling, and introduced a transaction-safe author mutation pipeline with phase receipts + rollback semantics across world generation, intelligent generation, targeted generation, and populate flows.
- Risk Level: `medium`

## Behavior Impact

- User-visible changes:
  - Author mutation endpoints now include `operation_receipt` metadata and optional `warnings` fields.
- Non-user-visible changes:
  - Added thread-safe cache access in `TTLCacheMap`.
  - Added per-session mutation locks around `/api/next`, `/api/action`, `/api/action/stream` commit path, and `/api/turn`.
  - Added config-driven session consistency mode selection (`cache`, `stateless`, `shared_cache` alias fallback).
  - Centralized author ingest/write orchestration in `postprocess_new_storylets` with one core transaction and explicit receipt phases.
  - Added rollback-safe behavior for coordinate-assignment failure in world generation.
- Explicit non-goals:
  - No route/path changes for existing `/api/*` and `/author/*` endpoints.
  - No schema migration changes.

## Validation Results

- `python -m pytest -q tests/service/test_session_service.py tests/integration/test_concurrent_session_requests.py` -> pass (`12 passed`)
- `python -m pytest -q tests/api/test_author_generation.py tests/integration/test_author_pipeline_transactions.py` -> pass (`4 passed`)
- `python -m pytest -q` -> pass (`516 passed`)
- `npm --prefix client run build` -> pass (Vite production build successful)

## Contract and Compatibility

- Contract/API changes: Additive only (`operation_receipt`/`warnings` fields in author responses).
- Migration/state changes: none.
- Backward compatibility: Existing route paths and baseline response fields remain unchanged.

## Metrics (if applicable)

- Baseline:
  - Not captured in this PR.
- After:
  - Not captured in this PR.

## Risks

- Per-session locking can reduce same-session throughput under high contention.
- `WW_SESSION_CONSISTENCY_MODE=shared_cache` currently falls back to stateless semantics until an external cache is implemented.
- Author pipeline receipts add payload verbosity for author endpoints.

## Rollback Plan

- Fast disable path:
  - Set `WW_SESSION_CONSISTENCY_MODE=cache` for legacy local cache behavior.
  - Revert to prior author write flow by reverting `storylet_ingest` transaction orchestration and endpoint receipt wiring.
- Full revert path:
  - Revert commits touching:
    - `src/services/session_service.py`
    - `src/services/cache.py`
    - `src/api/game/action.py`
    - `src/api/game/story.py`
    - `src/api/game/turn.py`
    - `src/services/storylet_ingest.py`
    - `src/api/author/world.py`
    - `src/api/author/generate.py`
    - `src/api/author/populate.py`
    - `src/services/world_bootstrap_service.py`
    - `src/services/spatial_navigator.py`

## Follow-up Work

- Implement real external shared cache + distributed lock support for `WW_SESSION_CONSISTENCY_MODE=shared_cache`.
- Add observability counters for session-lock contention and author pipeline phase durations.
