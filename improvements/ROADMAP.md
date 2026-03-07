# Roadmap

## Current State

**All v3 queue items are complete.** The codebase is ready for live lane-matrix sweep runs.

- Product status: Scene-card JIT narration, motif instrumentation, sweep harnesses, non-canon projection BFS expansion, canon-safe commit/invalidation enforcement, projection-seeded narration/hint diagnostics, additive turn fallback/clarity diagnostics, projection/clarity harness metrics, structured world-fact channel, adaptive projection pruning with pressure telemetry, v3 smoke/soak gates, lane-matrix sweep operationalization, and bootstrap critical-path diagnostics are all operational. State manager is modularized into typed domain components.
- Architecture status: 3-layer model lanes with per-lane temperature axes, reducer authority enforced, projection runtime budgets/flags with adaptive pruning tiers, commit-boundary invalidation enforced, projection-seeded adaptation context wired, six-component composite score (latency + motif + failure + projection + clarity + narrator), AdvancedStateManager decomposed into 4 typed domains, schema-first world-fact extraction, `bootstrap_diagnostics` in every session bootstrap/start response, v3 smoke + soak gates green (807 tests, quality-strict clean).
- Next action: run a live v3 lane-matrix sweep using the commands in README or `improvements/harness/10-SWEEP_METRICS_RUBRIC.md`.

## Guardrails

1. No route/path contract breaks without explicit approval; new diagnostics must be additive.
2. Reducer remains the only canonical world-state mutation authority.
3. Projection data is always non-canon until commit and must be invalidated after conflicting commits.
4. Every major/minor item must include executable validation commands and PR evidence.
5. v3 lane and budget work must be feature-flagged with safe defaults and rollback paths.

## Major Queue

*Empty — all majors complete and archived.*

## Minor Queue

*Empty — all minors complete and archived.*

## Completed Work (v3 cycle)

Architecture block:

1. ✅ Minor `113` — narrator/referee temp call-site audit.
2. ✅ Major `109` — unified turn pipeline: `turn_source`/`pipeline_mode` on every turn; choice-button turns consequence-grounded via `chosen_action`; `ack_line` in diagnostics.
3. ✅ Major `108` — unified `/session/start` route; `turn_source="initial_scene"` in diagnostics.
4. ✅ Minor `112` — turn-source stratified harness metrics (choice vs. freeform split).

Sweep infrastructure block:

5. ✅ Minor `115` — clarity distribution quality gate; `clarity_distribution_score`/`clarity_health_check`; documented in `10-SWEEP_METRICS_RUBRIC.md`.
6. ✅ Major `110` — lane-stratified sweep axes; `llm_narrator_temperature`/`llm_referee_temperature` LHS axes replacing legacy `llm_temperature`.
7. ✅ Major `111` — projection quality and clarity in composite score; six-component formula; `projection_health_summary` and `clarity_ranked_results` in phase summaries.
8. ✅ Minor `114` — per-lane harness diagnostics: `narrator_parse_success_rate`, `referee_decision_valid_rate`, `narrator_revise_decision_rate`.
9. ✅ Minor `116` — batched world storylet generation; token-budget truncation fix; batches of 6 with cross-batch deduplication.
10. ✅ Minor `117` — clarity in composite score; weight 0.10; latency 0.10→0.05, projection 0.15→0.10.
11. ✅ **Major `104`** — lane-matrix and projection-budget sweeps operationalized; `LaneBudgetVariant` axis cross-product; `_validate_shared_seed_schedule` fairness guard; `lane_budget_axes`/`seed_schedule`/`quality_gate_outcomes` in phase-A manifest; `_rank_phase_results_by_projection_efficiency` secondary ranking; 23 harness integration tests; lane-matrix CLI examples in README and Gate 5a in `04-QUALITY_GATES.md`.

Hardening block:

12. ✅ Major `105` — AdvancedStateManager modularized into 4 typed domain components.
13. ✅ Minor `106` — state-domain contract tests and migration fixtures.
14. ✅ Major `106` — schema-first world-fact channel via WorldFactPayload; `fact-audit` CLI command.
15. ✅ Minor `107` — graph-fact dedupe and canonical entity audit command.
16. ✅ Minor `108` — world-fact parser failure telemetry and fallback reasons.
17. ✅ Major `107` — adaptive projection pruning with pressure tiers; `budget_exhaustion_cause` tracking.
18. ✅ Minor `109` — projection budget pressure metrics in runtime and harness context_summary.
19. ✅ Minor `105` — v3 smoke gate docs + commands; Gate 2a in `04-QUALITY_GATES.md`.
20. ✅ Minor `110` — long-run soak scenarios; Gate 6 documented.
21. ✅ **Minor `111`** — bootstrap critical-path doc (`11-BOOTSTRAP_CRITICAL_PATH.md`); `bootstrap_diagnostics` field in `SessionBootstrapResponse`/`SessionStartResponse`; 2 contract tests.

## Notes

- All v3 queue items are archived in `improvements/majors/archive/` and `improvements/minors/archive/`.
- Historical implementation evidence remains in `improvements/history/`.
- V3 prioritizes coherence, canon safety, and reproducible evaluation over feature breadth.
- 807 tests pass, `quality-strict` clean (14 warnings, all within budget).
- Frontend v3 stub anchors are in place at `client/src/app/v3NarratorStubs.ts` and `client/src/hooks/useTurnOrchestration.ts` to guide world/scene/player narrator integration without changing current behavior.
