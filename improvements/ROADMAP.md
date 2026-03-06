# Roadmap

## Current State

- Product status: Scene-card JIT narration, motif instrumentation, sweep harnesses, and non-canon projection BFS expansion are operational. The next milestone is v3 projection-seeded orchestration across scene and hint lanes with stricter canon invalidation.
- Architecture status: 3-layer model lanes exist, reducer authority exists, projection runtime budgets/flags exist, and sweep metrics are mature for latency/motif/failure. Remaining gaps are projection-seeded narration integration, canon-safe invalidation, and lane-matrix operational evaluation.
- Top risks:
  - Projection expansion can increase latency/cost if runtime budgets are not enforced.
  - Speculative branches can leak into canonical state without strict reducer boundaries.
  - Comparative lane sweeps can produce misleading conclusions if seeds, lane configs, and diagnostics are not held constant.

## Guardrails

1. No route/path contract breaks without explicit approval; new diagnostics must be additive.
2. Reducer remains the only canonical world-state mutation authority.
3. Projection data is always non-canon until commit and must be invalidated after conflicting commits.
4. Every major/minor item must include executable validation commands and PR evidence.
5. v3 lane and budget work must be feature-flagged with safe defaults and rollback paths.

## Major Queue

1. `102-integrate-projection-seeded-scene-and-player-narration.md`
2. `103-enforce-reducer-only-canon-commit-and-projection-invalidation.md`
3. `104-operationalize-v3-model-lane-matrix-and-projection-budget-sweeps.md`

## Minor Queue

1. `102-add-projection-and-clarity-metrics-to-harness-artifacts.md`
2. `103-add-additive-map-clarity-and-fallback-reason-fields.md`
3. `105-add-v3-smoke-scenarios-and-gate-commands.md`

## Recommended Execution Order

1. Implement major `103` (canon commit boundary and projection invalidation) before widening projection usage.
2. Implement major `102` (projection-seeded narration and player hints).
3. Implement minor `103` (additive diagnostics fields) and minor `102` (projection metrics) together.
4. Implement major `104` (lane matrix and projection-budget sweeps) for end-to-end evaluation.
5. Close with minor `105` (v3 smoke gate docs/commands).

## Notes

- This is a v3 queue reset. Previously active non-v3 items were moved to `improvements/majors/archive/` and `improvements/minors/archive/`.
- Historical implementation evidence remains in `improvements/history/` and archived item docs.
- V3 prioritizes coherence, canon safety, and reproducible evaluation over feature breadth.
- Completed in this cycle: minor `101` (LLM playtest guide refresh + README protocol link), minor `104` (v3 runtime budgets/flags), and major `101` (non-canon projection BFS planner).
- Frontend v3 stub anchors are in place at `client/src/app/v3NarratorStubs.ts` and `client/src/hooks/useTurnOrchestration.ts` to guide world/scene/player narrator integration without changing current behavior.
