# Roadmap

## Current State

- Product status: Scene-card JIT narration, motif instrumentation, sweep harnesses, non-canon projection BFS expansion, and canon-safe commit/invalidation enforcement are operational. The next milestone is v3 projection-seeded orchestration across scene and hint lanes.
- Architecture status: 3-layer model lanes exist, reducer authority exists, projection runtime budgets/flags exist, commit-boundary invalidation is enforced, and sweep metrics are mature for latency/motif/failure. Remaining gaps are projection-seeded narration integration and lane-matrix operational evaluation.
- Top risks:
  - Projection expansion can increase latency/cost if runtime budgets are not enforced.
  - Regressions can reintroduce non-canon leakage if reducer guards or invalidation hooks are bypassed.
  - `AdvancedStateManager` scope growth can reduce maintainability and increase regression blast radius.
  - Heuristic world-fact extraction can silently drift under model-output variance, creating graph noise.
  - Comparative lane sweeps can produce misleading conclusions if seeds, lane configs, and diagnostics are not held constant.

## Guardrails

1. No route/path contract breaks without explicit approval; new diagnostics must be additive.
2. Reducer remains the only canonical world-state mutation authority.
3. Projection data is always non-canon until commit and must be invalidated after conflicting commits.
4. Every major/minor item must include executable validation commands and PR evidence.
5. v3 lane and budget work must be feature-flagged with safe defaults and rollback paths.

## Major Queue

1. `102-integrate-projection-seeded-scene-and-player-narration.md`
2. `104-operationalize-v3-model-lane-matrix-and-projection-budget-sweeps.md`
3. `105-modularize-advanced-state-manager-into-domain-state-components.md`
4. `106-replace-heuristic-graph-fact-extraction-with-structured-world-fact-channel.md`
5. `107-harden-projection-budgets-with-adaptive-pruning-and-latency-guards.md`

## Minor Queue

1. `102-add-projection-and-clarity-metrics-to-harness-artifacts.md`
2. `103-add-additive-map-clarity-and-fallback-reason-fields.md`
3. `105-add-v3-smoke-scenarios-and-gate-commands.md`
4. `106-add-state-domain-contract-tests-and-migration-fixtures.md`
5. `107-add-graph-fact-dedupe-and-canonical-entity-audit-command.md`
6. `108-add-world-fact-parser-failure-telemetry-and-fallback-reasons.md`
7. `109-add-projection-budget-pressure-metrics-to-runtime-and-harness.md`
8. `110-add-long-run-soak-scenarios-for-graph-and-projection-drift.md`

## Recommended Execution Order

1. Implement major `102` (projection-seeded narration and player hints).
2. Implement minor `103` (additive diagnostics fields) and minor `102` (projection metrics) together.
3. Implement major `104` (lane matrix and projection-budget sweeps) for end-to-end evaluation baseline.
4. Implement major `105` (state-manager modularization) and minor `106` (state-domain parity fixtures).
5. Implement major `106` (structured world-fact channel) with minors `107` (dedupe audit command) and `108` (parser/fallback telemetry).
6. Implement major `107` (adaptive pruning/latency guards) with minor `109` (pressure metrics).
7. Close with minor `105` (v3 smoke gate docs/commands) and minor `110` (long-run drift soak scenarios).

## Notes

- This is a v3 queue reset. Previously active non-v3 items were moved to `improvements/majors/archive/` and `improvements/minors/archive/`.
- Historical implementation evidence remains in `improvements/history/` and archived item docs.
- V3 prioritizes coherence, canon safety, and reproducible evaluation over feature breadth.
- Completed in this cycle: minor `101` (LLM playtest guide refresh + README protocol link), minor `104` (v3 runtime budgets/flags), major `101` (non-canon projection BFS planner), and major `103` (reducer-only canon commit + projection invalidation enforcement).
- Newly added hardening focus areas (post-feedback): state-manager decomposition, schema-first graph fact ingestion, and projection pressure/pruning controls.
- Frontend v3 stub anchors are in place at `client/src/app/v3NarratorStubs.ts` and `client/src/hooks/useTurnOrchestration.ts` to guide world/scene/player narrator integration without changing current behavior.
