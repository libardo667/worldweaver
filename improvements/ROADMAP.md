# Roadmap

## Current State

- Product status: Scene-card JIT narration, motif instrumentation, sweep harnesses, non-canon projection BFS expansion, canon-safe commit/invalidation enforcement, projection-seeded narration/hint diagnostics, additive turn fallback/clarity diagnostics, and projection/clarity harness metrics are operational. The next milestone is v3 lane-matrix operational evaluation and hardening work.
- Architecture status: 3-layer model lanes exist, reducer authority exists, projection runtime budgets/flags exist, commit-boundary invalidation is enforced, projection-seeded adaptation context is wired, and sweep metrics are mature for latency/motif/failure plus projection/clarity quality. Remaining gaps are lane-matrix operational evaluation plus hardening tracks.
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

1. `104-operationalize-v3-model-lane-matrix-and-projection-budget-sweeps.md`
2. `105-modularize-advanced-state-manager-into-domain-state-components.md`
3. `106-replace-heuristic-graph-fact-extraction-with-structured-world-fact-channel.md`
4. `107-harden-projection-budgets-with-adaptive-pruning-and-latency-guards.md`
5. `108-unify-session-start-with-bootstrap-seeded-first-turn.md`
6. `109-unify-choice-and-freeform-turn-orchestration-pipeline.md`
7. `110-stratify-sweep-parameter-axes-by-model-lane.md`
8. `111-incorporate-projection-quality-and-clarity-into-composite-score.md`

## Minor Queue

1. `105-add-v3-smoke-scenarios-and-gate-commands.md`
2. `106-add-state-domain-contract-tests-and-migration-fixtures.md`
3. `107-add-graph-fact-dedupe-and-canonical-entity-audit-command.md`
4. `108-add-world-fact-parser-failure-telemetry-and-fallback-reasons.md`
5. `109-add-projection-budget-pressure-metrics-to-runtime-and-harness.md`
6. `110-add-long-run-soak-scenarios-for-graph-and-projection-drift.md`
7. `111-add-bootstrap-seeding-critical-path-and-prompt-surface-report.md`
8. `112-add-turn-source-stratified-harness-metrics-and-evidence.md`
9. `113-audit-and-normalize-narrator-referee-temperature-call-sites.md`
10. `114-add-per-lane-harness-diagnostics-narrator-parse-and-referee-validity.md`
11. `115-add-clarity-distribution-as-sweep-quality-gate.md`

## Recommended Execution Order

Architecture-first block (do before any further sweeps so baselines reflect intended design):

1. ✅ Minor `113` — narrator/referee temp call-site audit (done).
2. ✅ Major `109` — unified turn pipeline diagnostics: `turn_source`/`pipeline_mode` in every `_ww_diag`; action path now checks projection stubs for hint channel parity (done).
3. ✅ Major `108` — unified `/session/start` route; first turn uses same `run_next_turn_orchestration` call as `/next`; `turn_source="initial_scene"` in diagnostics (done).
4. ✅ Minor `112` — turn-source stratified harness metrics (choice vs. freeform split visible in every run); no route dependency, additive only (done).

Sweep infrastructure block (quality gates and lane axes, now on correct foundation):

5. ✅ Minor `115` (clarity distribution quality gate) — `clarity_distribution_score`, `clarity_health_check`, per-run `clarity_health_warning`, phase `clarity_distribution_score_avg`/`clarity_health_flags`; documented in `improvements/harness/10-SWEEP_METRICS_RUBRIC.md` (done).
5. Major `110` (lane-stratified sweep axes) — per-lane narrator/referee temperature axes; minor `113` prereq is complete.
6. Major `111` (projection quality and clarity in composite score) — depends on clarity score function from minor `115`.
7. Minor `114` (per-lane harness diagnostics) — alongside or after major `110`; adds lane-level observability.
8. Major `104` (lane matrix and projection-budget sweeps) — end-to-end evaluation baseline, now with correct per-lane axes. Before running: read `improvements/harness/10-SWEEP_METRICS_RUBRIC.md` for the full metric reference and "reading a run artifact" checklist; all fields emitted by the harness are documented there.

Hardening block:

9. Major `105` (state-manager modularization) and minor `106` (state-domain parity fixtures).
10. Major `106` (structured world-fact channel) with minors `107` (dedupe audit command) and `108` (parser/fallback telemetry).
11. Major `107` (adaptive pruning/latency guards) with minor `109` (pressure metrics).
12. Close with minor `105` (v3 smoke gate docs/commands) and minor `110` (long-run drift soak scenarios).
13. Major `109` — unify choice and freeform turn orchestration pipeline (minor `112` metrics will already make the split observable before this unification).

## Notes

- This is a v3 queue reset. Previously active non-v3 items were moved to `improvements/majors/archive/` and `improvements/minors/archive/`.
- Historical implementation evidence remains in `improvements/history/` and archived item docs.
- V3 prioritizes coherence, canon safety, and reproducible evaluation over feature breadth.
- Completed in this cycle: minor `101` (LLM playtest guide refresh + README protocol link), minor `104` (v3 runtime budgets/flags), minor `102` (projection/clarity harness metrics), minor `103` (additive map-clarity + fallback diagnostics), major `101` (non-canon projection BFS planner), major `102` (projection-seeded scene narration + player hint channel diagnostics), major `103` (reducer-only canon commit + projection invalidation enforcement), minor `113` (narrator/referee temperature call-site audit and normalization), major `109` (unified turn pipeline diagnostics — `turn_source`/`pipeline_mode` on every turn; action path projection-hint parity), major `108` (unified `/session/start` route returning bootstrap + first playable turn), minor `112` (turn-source stratified harness metrics — `stratified_metrics` with per-source latency/failure/projection/clarity slices in every run summary and phase aggregate), and minor `115` (clarity distribution quality gate — `clarity_distribution_score`/`clarity_health_check` functions, per-run `clarity_health_warning`, phase `clarity_distribution_score_avg`/`clarity_health_flags`, gate threshold and all harness metrics documented in `improvements/harness/10-SWEEP_METRICS_RUBRIC.md`).
- Newly added hardening focus areas (post-feedback): state-manager decomposition, schema-first graph fact ingestion, and projection pressure/pruning controls.
- Frontend v3 stub anchors are in place at `client/src/app/v3NarratorStubs.ts` and `client/src/hooks/useTurnOrchestration.ts` to guide world/scene/player narrator integration without changing current behavior.
