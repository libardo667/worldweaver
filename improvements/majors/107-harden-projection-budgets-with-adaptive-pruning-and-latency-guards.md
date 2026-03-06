# Harden projection budgets with adaptive pruning and latency guards

## Problem
Projection frontier expansion is computationally and token expensive. Without adaptive pruning and pressure-aware controls, background planning can spike latency/cost and degrade turn responsiveness as scenario complexity increases.

## Proposed Solution
Add pressure-aware projection controls that preserve coherence while enforcing hard runtime budgets.

1. Introduce projection pressure scoring using elapsed time, node expansion, queue depth, and budget headroom.
2. Implement adaptive branch pruning based on recency, location relevance, goal relevance, and confidence.
3. Add deterministic degradation tiers (full expansion -> trimmed expansion -> stubs-only) under budget pressure.
4. Emit structured telemetry for prune reasons, budget exhaustion cause, and frontier utility outcomes.
5. Keep behavior behind explicit runtime flags with conservative defaults and fast rollback toggles.

## Files Affected
- `src/services/prefetch_service.py`
- `src/services/turn_service.py`
- `src/services/runtime_metrics.py`
- `src/config.py`
- `tests/service/test_prefetch_service.py`
- `tests/service/test_projection_bfs.py`
- `tests/integration/test_parameter_sweep_harness.py`
- `tests/api/test_settings_readiness.py`

## Acceptance Criteria
- [ ] Projection expansion never exceeds configured hard depth/node/time budgets.
- [ ] Adaptive pruning reduces budget pressure without breaking turn continuity.
- [ ] Degradation tiers activate deterministically under pressure and recover when pressure drops.
- [ ] Telemetry includes prune reasons and pressure diagnostics for runtime/harness analysis.
- [ ] Feature flags allow immediate rollback to baseline projection behavior.

## Validation Commands
- `pytest -q tests/service/test_prefetch_service.py tests/service/test_projection_bfs.py`
- `pytest -q tests/integration/test_parameter_sweep_harness.py tests/api/test_settings_readiness.py`
- `python scripts/dev.py quality-strict`

## Risks & Rollback
- Risk: aggressive pruning can lower projection hit-rate and perceived coherence.
- Risk: adaptive controls can introduce nondeterminism if tie-breaking is unclear.
- Rollback: disable adaptive pruning flags and revert to existing bounded BFS expansion with current static budgets.
