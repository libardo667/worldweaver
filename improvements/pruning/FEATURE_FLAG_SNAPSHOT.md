# Feature Flag Snapshot (Wave 0)

Date: `2026-03-06`  
Context: non-pytest runtime settings load (`src.config.settings`)

## Snapshot Artifacts
- `FEATURE_FLAG_SNAPSHOT.csv`
- `V3_RUNTIME_BUDGET_SNAPSHOT.csv`

## Summary
- Total boolean feature flags in settings: `21`
- Flags diverging from code default in this runtime snapshot: `1`
- Override detected:
- `enable_constellation`: code default `false`, effective `true` (via `WW_ENABLE_CONSTELLATION` from `.env`/environment)

## Test-Only Overrides
- `tests/conftest.py` sets:
- `WW_ENABLE_CONSTELLATION=0`
- `WW_ENABLE_JIT_BEAT_GENERATION=0`
- `tests/service/test_action_validation_policy.py` mutates `settings.enable_strict_action_validation` during tests.

## V3 Runtime Budget Snapshot
- `frontier_prefetch_enabled`: `true`
- `projection_expansion_enabled`: `true`
- `player_hint_channel_enabled`: `true`
- `projection_seeded_narration_enabled`: `true`
- `max_projection_depth`: `2`
- `max_projection_nodes`: `12`
- `projection_time_budget_ms`: `120`
- `projection_ttl_seconds`: `180`
- `prefetch_ttl_seconds`: `180`

## Rollback Safety Note
- Keep these two CSV snapshots as the baseline reference before any pruning/migration that could alter runtime behavior gates.
