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
12. `116-batch-world-storylet-generation-to-fix-token-budget-truncation.md`
13. `117-add-clarity-distribution-score-to-composite-score.md`

## Recommended Execution Order

Architecture-first block (do before any further sweeps so baselines reflect intended design):

1. ✅ Minor `113` — narrator/referee temp call-site audit (done).
2. ✅ Major `109` — unified turn pipeline diagnostics + choice routing: `turn_source`/`pipeline_mode` in every `_ww_diag`; action path checks projection stubs for hint channel parity; `choice_label` added to `NextReq`, `chosen_action` wired through `adapt_storylet_to_context` so choice-button turns open with a consequence-grounded sentence; `ack_line` emitted in diagnostics for choice turns (done).
3. ✅ Major `108` — unified `/session/start` route; first turn uses same `run_next_turn_orchestration` call as `/next`; `turn_source="initial_scene"` in diagnostics (done).
4. ✅ Minor `112` — turn-source stratified harness metrics (choice vs. freeform split visible in every run); no route dependency, additive only (done).

Sweep infrastructure block (quality gates and lane axes, now on correct foundation):

5. ✅ Minor `115` (clarity distribution quality gate) — `clarity_distribution_score`, `clarity_health_check`, per-run `clarity_health_warning`, phase `clarity_distribution_score_avg`/`clarity_health_flags`; documented in `improvements/harness/10-SWEEP_METRICS_RUBRIC.md` (done).
6. ✅ Major `110` (lane-stratified sweep axes) — `SweepParameterSet` now has `llm_narrator_temperature` (range 0.4–1.2) and `llm_referee_temperature` (range 0.0–0.5) replacing the legacy `llm_temperature` axis; `build_parameter_env_overrides_from_values` injects `LLM_NARRATOR_TEMPERATURE`/`LLM_REFEREE_TEMPERATURE` and suppresses `LLM_TEMPERATURE` when per-lane values are provided; `RunConfig` carries per-lane temps in `llm_parameters` JSON; phase A dry-run records `env_overrides` with per-lane keys; tests in `test_parameter_sweep_phase_a.py` and `test_prompt_and_model.py` (done).
7. ✅ Major `111` (projection quality and clarity in composite score) — `score_run_metrics` gains `projection_hit_rate`/`projection_waste_rate` params (weights rebalanced to 0.50/0.20/0.05/0.10/0.15); `check_run_projection_health` emits per-run `projection_health_warnings`; phase summaries include `projection_health_summary` and `clarity_ranked_results`; `10-SWEEP_METRICS_RUBRIC.md` updated with new formula, projection health gate docs, and ranking view table (done).
8. ✅ Minor `114` (per-lane harness diagnostics) — `_run_motif_referee_audit` now returns `referee_decision_was_valid`; `adapt_storylet_to_context` records `narrator_parse_success`; `turn_service` propagates both into `_ww_diag`; `_lane_diagnostic_metrics` in the harness aggregates `narrator_parse_success_rate`, `referee_decision_valid_rate`, `narrator_revise_decision_rate` per run; `_aggregate_phase_b_metrics` includes all three; 6 new tests in `test_long_run_harness_helpers.py` (done).
9. ✅ Minor `116` (batched world storylet generation) — `generate_world_storylets` now loops in batches of 6, passing `existing_titles` to the referee each batch to enforce cross-batch variety; per-batch narrator render keeps token budget under the 2200-token referee cap; fallback returned when all batches fail; harness bootstrap gate tightened to reject `storylets_created < max(5, requested // 2)` as likely token truncation (done).
10. ✅ Minor `117` (clarity in composite score) — `score_run_metrics` adds `clarity_distribution_score` param (weight 0.10); latency weight reduced 0.10→0.05, projection weight reduced 0.15→0.10; neutral default 0.5 when absent for backward compat; `rank_phase_results` and Phase B scoring pass clarity through; `10-SWEEP_METRICS_RUBRIC.md` updated with new six-component formula (done).
11. Major `104` (lane matrix and projection-budget sweeps) — end-to-end evaluation baseline, now with correct per-lane axes and clarity-weighted composite score. Before running: read `improvements/harness/10-SWEEP_METRICS_RUBRIC.md` for the full metric reference and "reading a run artifact" checklist; all fields emitted by the harness are documented there.

Hardening block:

12. Major `105` (state-manager modularization) and minor `106` (state-domain parity fixtures).
13. Major `106` (structured world-fact channel) with minors `107` (dedupe audit command) and `108` (parser/fallback telemetry).
14. Major `107` (adaptive pruning/latency guards) with minor `109` (pressure metrics).
15. Close with minor `105` (v3 smoke gate docs/commands) and minor `110` (long-run drift soak scenarios).

## Notes

- This is a v3 queue reset. Previously active non-v3 items were moved to `improvements/majors/archive/` and `improvements/minors/archive/`.
- Historical implementation evidence remains in `improvements/history/` and archived item docs.
- V3 prioritizes coherence, canon safety, and reproducible evaluation over feature breadth.
- Completed in this cycle (latest): minor `117` (clarity distribution score in composite — `score_run_metrics` gains `clarity_distribution_score` at weight 0.10; latency reduced 0.10→0.05, projection 0.15→0.10; neutral default 0.5 preserves backward compat; Phase B candidate selection now incentivized by the most direct V3 Pillar 3 signal); major `109` full choice routing (choice-button turns now produce consequence-grounded narration — `choice_label` added to `NextReq`, `chosen_action` flows into `adapt_storylet_to_context`, narrator prompted to open with the immediate consequence of the specific choice made, `ack_line` emitted in turn diagnostics); `quality-strict` gate restored to green — 7 pre-existing test failures fixed (4 action-endpoint tests + 1 concurrent test: tests now pin `enable_strict_three_layer_architecture=False` since `.env` enables it; 2 settings-readiness tests: now pin `enable_projection_referee_scoring=False`); black formatting applied across 20 files.
- Completed in this cycle: minor `101` (LLM playtest guide refresh + README protocol link), minor `104` (v3 runtime budgets/flags), minor `102` (projection/clarity harness metrics), minor `103` (additive map-clarity + fallback diagnostics), major `101` (non-canon projection BFS planner), major `102` (projection-seeded scene narration + player hint channel diagnostics), major `103` (reducer-only canon commit + projection invalidation enforcement), minor `113` (narrator/referee temperature call-site audit and normalization), major `109` (unified turn pipeline diagnostics — `turn_source`/`pipeline_mode` on every turn; action path projection-hint parity; choice-button turns now consequence-grounded via `chosen_action` in adaptation context), major `108` (unified `/session/start` route returning bootstrap + first playable turn), minor `112` (turn-source stratified harness metrics — `stratified_metrics` with per-source latency/failure/projection/clarity slices in every run summary and phase aggregate), minor `115` (clarity distribution quality gate — `clarity_distribution_score`/`clarity_health_check` functions, per-run `clarity_health_warning`, phase `clarity_distribution_score_avg`/`clarity_health_flags`, gate threshold and all harness metrics documented in `improvements/harness/10-SWEEP_METRICS_RUBRIC.md`), major `110` (lane-stratified sweep parameter axes — `SweepParameterSet` replaces `llm_temperature` with independent `llm_narrator_temperature`/`llm_referee_temperature` LHS axes; `build_parameter_env_overrides_from_values` injects `LLM_NARRATOR_TEMPERATURE`/`LLM_REFEREE_TEMPERATURE` and suppresses legacy `LLM_TEMPERATURE` when per-lane values are set), minor `116` (batched world storylet generation — token-budget truncation fix; batches of 6 with cross-batch deduplication), and minor `117` (clarity in composite score — six-component formula, clarity weight 0.10, latency/projection weights reduced).
- Newly added hardening focus areas (post-feedback): state-manager decomposition, schema-first graph fact ingestion, and projection pressure/pruning controls.
- Frontend v3 stub anchors are in place at `client/src/app/v3NarratorStubs.ts` and `client/src/hooks/useTurnOrchestration.ts` to guide world/scene/player narrator integration without changing current behavior.
