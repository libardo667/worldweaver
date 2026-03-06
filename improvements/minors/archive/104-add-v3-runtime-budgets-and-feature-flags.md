# Add v3 runtime budgets and feature flags for projection expansion

## Problem
v3 introduced new background expansion work and multi-lane decisions. Without explicit runtime controls, operators could not bound cost, latency, or rollout blast radius.

## Proposed Solution
Added environment-configurable runtime budgets and feature flags.

- Flags: enable/disable projection expansion, player hint channel, projection-seeded narration, and projection referee scoring.
- Budgets: max projection depth, max nodes, per-turn expansion time budget, and TTL defaults.
- Surfaced effective runtime settings in readiness/diagnostics output for reproducibility.

## Files Affected
- `src/config.py`
- `src/services/prefetch_service.py`
- `src/services/turn_service.py`
- `src/api/game/state.py`
- `src/api/game/settings_api.py`
- `tests/api/test_settings_readiness.py`
- `tests/service/test_prefetch_service.py`

## Acceptance Criteria
- [x] New flags and budgets are environment-configurable with safe defaults.
- [x] Runtime honors limits during expansion.
- [x] Effective settings are visible in diagnostics/readiness output.
- [x] Settings tests cover defaults and override behavior.

## Validation Commands
- `pytest -q tests/api/test_settings_readiness.py tests/service/test_prefetch_service.py`
- `python scripts/dev.py quality-strict`

## Completion Note
- Status: done
- Archive target: `improvements/minors/archive/104-add-v3-runtime-budgets-and-feature-flags.md`
