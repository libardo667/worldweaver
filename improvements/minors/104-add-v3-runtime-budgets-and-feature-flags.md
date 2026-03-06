# Add v3 runtime budgets and feature flags for projection expansion

## Problem
v3 introduces new background expansion work and multi-lane decisions. Without explicit runtime controls, operators cannot bound cost, latency, or rollout blast radius.

## Proposed Solution
Add environment-configurable runtime budgets and feature flags.

- Flags: enable/disable projection expansion, player hint channel, projection-seeded narration.
- Budgets: max projection depth, max nodes, per-turn expansion time budget, and TTL defaults.
- Surface active settings in diagnostics endpoints/logs for reproducibility.

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
