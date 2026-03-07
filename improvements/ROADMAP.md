# Roadmap

## Current State

- Product status: Scene-card JIT narration, motif instrumentation, sweep harnesses, non-canon projection BFS expansion, canon-safe commit/invalidation enforcement, projection-seeded narration/hint diagnostics, additive turn fallback/clarity diagnostics, projection/clarity harness metrics, structured world-fact channel, adaptive projection pruning with pressure telemetry, v3 smoke and soak gates are all operational. State manager is modularized into typed domain components. **The sole remaining milestone is Major 104: end-to-end v3 lane-matrix evaluation sweep.**
- Architecture status: 3-layer model lanes exist with per-lane temperature axes, reducer authority enforced, projection runtime budgets/flags exist with adaptive pruning tiers, commit-boundary invalidation enforced, projection-seeded adaptation context wired, sweep metrics mature for latency/motif/failure/projection/clarity (six-component composite score), AdvancedStateManager decomposed into InventoryDomain/RelationshipDomain/GoalDomain/NarrativeBeatsDomain, schema-first world-fact extraction via WorldFactPayload with heuristic fallback, v3 smoke + soak gates documented and green.
- Top risks:
  - Lane-matrix sweeps can produce misleading baselines if seeds, lane configs, and diagnostics are not held constant across runs.
  - Projection expansion cost can grow without budget monitoring (mitigated: adaptive pruning + pressure metrics now operational).

## Guardrails

1. No route/path contract breaks without explicit approval; new diagnostics must be additive.
2. Reducer remains the only canonical world-state mutation authority.
3. Projection data is always non-canon until commit and must be invalidated after conflicting commits.
4. Every major/minor item must include executable validation commands and PR evidence.
5. v3 lane and budget work must be feature-flagged with safe defaults and rollback paths.

## Major Queue

1. `104-operationalize-v3-model-lane-matrix-and-projection-budget-sweeps.md` ← **only remaining major**

## Minor Queue

1. `111-add-bootstrap-seeding-critical-path-and-prompt-surface-report.md` ← **only remaining minor**

## Recommended Execution Order

Everything below is ✅ done. Only Major `104` and Minor `111` remain.

Architecture block (complete):

1. ✅ Minor `113` — narrator/referee temp call-site audit.
2. ✅ Major `109` — unified turn pipeline: `turn_source`/`pipeline_mode` on every turn; choice-button turns consequence-grounded via `chosen_action`; `ack_line` in diagnostics.
3. ✅ Major `108` — unified `/session/start` route; `turn_source="initial_scene"` in diagnostics.
4. ✅ Minor `112` — turn-source stratified harness metrics (choice vs. freeform split).

Sweep infrastructure block (complete):

5. ✅ Minor `115` — clarity distribution quality gate; `clarity_distribution_score`/`clarity_health_check`; documented in `10-SWEEP_METRICS_RUBRIC.md`.
6. ✅ Major `110` — lane-stratified sweep axes; `llm_narrator_temperature`/`llm_referee_temperature` LHS axes replacing legacy `llm_temperature`.
7. ✅ Major `111` — projection quality and clarity in composite score; six-component formula; `projection_health_summary` and `clarity_ranked_results` in phase summaries.
8. ✅ Minor `114` — per-lane harness diagnostics: `narrator_parse_success_rate`, `referee_decision_valid_rate`, `narrator_revise_decision_rate`.
9. ✅ Minor `116` — batched world storylet generation; token-budget truncation fix; batches of 6 with cross-batch deduplication.
10. ✅ Minor `117` — clarity in composite score; weight 0.10; latency 0.10→0.05, projection 0.15→0.10.
11. ➡️ **Major `104`** — lane matrix and projection-budget sweeps; end-to-end evaluation baseline with correct per-lane axes and clarity-weighted composite score. Before running: read `improvements/harness/10-SWEEP_METRICS_RUBRIC.md`.

Hardening block (complete):

12. ✅ Major `105` — AdvancedStateManager modularized into 4 typed domain components (InventoryDomain, RelationshipDomain, GoalDomain, NarrativeBeatsDomain); property facades maintain backward compat; change_history owned by orchestrator.
13. ✅ Minor `106` — state-domain contract tests and migration fixtures; v1/v2/partial snapshot round-trips; domain invariant tests.
14. ✅ Major `106` — schema-first world-fact channel via WorldFactPayload; `__world_facts__` delta key; heuristic fallback with provenance tagging; `audit_graph_facts` read-only scan; `fact-audit` CLI command.
15. ✅ Minor `107` — graph-fact dedupe and canonical entity audit command.
16. ✅ Minor `108` — world-fact parser failure telemetry and fallback reasons in runtime_metrics.
17. ✅ Major `107` — adaptive projection pruning with pressure tiers; `_compute_projection_pressure`/`_pressure_tier`/`_should_prune_bfs_node`; `budget_exhaustion_cause` tracking; conservative defaults (flags off).
18. ✅ Minor `109` — projection budget pressure metrics in runtime and harness; `_PROJECTION_PRESSURE_COUNTERS`; `pressure_tier`/`nodes_pruned`/`prune_reason_distribution`/`budget_exhaustion_cause` in context_summary; `adaptive_pruning_enabled`/`pressure_tiers_enabled` in readiness response.
19. ✅ Minor `105` — v3 smoke gate docs + commands; Gate 2a documented in `04-QUALITY_GATES.md`; smoke tests in `test_turn_progression_simulation.py`.
20. ✅ Minor `110` — long-run soak scenarios; soak gate (Gate 6) documented; node-budget, counter-monotonicity, and pruned-node telemetry consistency tests.

Remaining:

21. ➡️ **Minor `111`** — bootstrap seeding critical path and prompt surface report.

## Notes

- This is a v3 queue reset. Previously active non-v3 items were moved to `improvements/majors/archive/` and `improvements/minors/archive/`.
- Historical implementation evidence remains in `improvements/history/` and archived item docs.
- V3 prioritizes coherence, canon safety, and reproducible evaluation over feature breadth.
- All hardening work is complete and green (782 tests pass, `quality-strict` clean).
- Frontend v3 stub anchors are in place at `client/src/app/v3NarratorStubs.ts` and `client/src/hooks/useTurnOrchestration.ts` to guide world/scene/player narrator integration without changing current behavior.
