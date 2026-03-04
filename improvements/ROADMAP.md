# Roadmap

## Current State

- Product status: Explore, Reflect, and Constellation debug modes are shipped; onboarding/bootstrap alignment and narrative evaluation harness are integrated.
- Architecture status: Behavior-preserving refactor is complete through major `37`; compass/spatial optional-assistive demotion close-out (`47`, `66`, `68`), naming cleanup (`49`), runtime LLM latency/token metrics closure (`44`), and local runtime operationalization (`46`) are complete and archived.
- Top risks:
  - Class A narrative coherence and onboarding latency: batch storylet generation produces disconnected vignettes and 30-60s waits; addressed by major `51` and minor `71`.
  - Class A latency/cost variability remains in runtime LLM paths; local observability is now present, but metrics are still in-memory/local-process only.
  - Class C UX completeness risk was concentrated in minor `65`; implementation is now in `verify` pending global test-baseline cleanup.
  - Class C onboarding/config UX risk: missing API key/model setup is still implicit for fresh local users until startup setup gating + settings surface are shipped (`90`, `91`, `92`).
  - Class B static hygiene debt remains high: `ruff` repo-scope check is still red (121 violations) and `black --check` reports 27 files to reformat.
  - Compose/runtime assets can drift from host workflows unless `scripts/dev.py` remains the canonical command surface.

## Guardrails

1. No API route/path/payload shape changes unless explicitly approved.
2. Keep API layers thin (routing/validation only) and consolidate logic in services.
3. Prefer delete/merge/demote/isolate over new abstraction growth when pruning.
4. Keep lane file boundaries and contract ownership explicit before implementation.
5. Run required gates per item and final integration gates: `python -m pytest -q` and `npm --prefix client run build`.
6. Track repo-wide lint as debt (`python scripts/dev.py lint --all`) but keep it non-blocking until major `50` is complete.
7. Record evidence, unresolved risk, and rollback notes for every major/minor closure.

## Major Queue

1. [P1][Complete] `51-jit-beat-generation-pipeline.md` (replace batch storylet generation with world-bible + JIT beat generation for narrative coherence and onboarding speed).
2. [P2][Deferred Non-Blocking] `50-establish-full-project-lint-baseline-and-ci-gates.md` (execute staged lint debt burn-down, then re-enable strict Gate 3 enforcement).

## Minor Queue

1. [P0][Complete] `71-switch-default-llm-to-fluency-model.md`.
2. [P1][Complete] `72-add-jit-beat-generation-feature-flag.md` (safety flag for major 51 rollout).
3. [P1][Complete] `73-add-world-bible-prompt-and-generator.md` (fast world bible LLM function).
4. [P1][Complete] `74-add-jit-beat-generation-function.md` (per-turn JIT beat LLM function + prompt).
5. [P1][Complete] `75-wire-jit-pipeline-bootstrap-and-api.md` (end-to-end wiring, arc tracking).
6. [P1][Verify] `65-add-constellation-graph-view-v1.md` (node-link graph implemented; awaiting green global test baseline).
7. [P0][Complete] `90-add-startup-setup-modal-for-missing-api-key-or-model.md`.
8. [P0][Complete] `91-retrigger-setup-modal-after-dev-hard-reset-when-env-is-incomplete.md`.
9. [P1][Complete] `92-add-global-settings-menu-for-model-key-and-runtime-toggles.md`.

## Intake Queue (Operationalized on March 3, 2026)

Mapped existing item:

1. [P1][Verify] `65-add-constellation-graph-view-v1.md` (covers constellation graph parity closure).

New major candidates:

1. [P1][Pending] `52-harden-world-memory-fact-graph-identities-and-relationships.md`.
2. [P1][Complete] `53-make-world-projection-deterministic-explainable-and-replayable.md`.
3. [P1][Pending] `54-enforce-freeform-action-grounding-against-facts-and-constraints.md`.
4. [P1][Pending] `55-implement-structure-first-runtime-storylet-supply-chain.md`.
5. [P1][Pending] `56-promote-goal-and-arc-to-first-class-selection-lens.md`.
6. [P1][Pending] `57-harden-session-cache-thread-safety-and-worker-strategy.md`.
7. [P1][Pending] `58-make-author-generation-pipeline-transaction-safe.md`.
8. [P1][Pending] `59-introduce-authoritative-event-reducer-and-rulebook.md`.
9. [P1][Pending] `60-add-deterministic-world-simulation-systems-per-turn.md`.
10. [P1][Pending] `61-unify-turn-orchestration-across-next-and-action.md`.

New minor candidates:

1. [P1][Pending] `76-add-staged-lint-baseline-gates-for-newly-touched-files.md`.
2. [P1][Pending] `77-make-llm-calls-non-blocking-in-request-paths.md`.
3. [P1][Pending] `78-unify-llm-json-extraction-and-schema-validation.md`.
4. [P1][Pending] `79-add-auth-and-rate-limits-to-author-and-generation-endpoints.md`.
5. [P1][Pending] `80-add-structured-logging-and-request-correlation-ids.md`.
6. [P1][Pending] `81-audit-archived-improvements-against-acceptance-criteria.md`.
7. [P2][Pending] `82-refresh-claude-docs-to-match-current-runtime-and-prompting.md`.
8. [P1][Pending] `83-add-env-example-and-golden-path-verify-command.md`.
9. [P1][Pending] `84-extend-narrative-eval-harness-with-coherence-metrics.md`.
10. [P1][Pending] `85-canonicalize-danger-aliases-to-environment-danger-level.md`.
11. [P1][Pending] `86-move-choice-inc-dec-application-to-server-reducer.md`.
12. [P1][Pending] `87-add-variable-schema-and-clamp-policies-for-core-state.md`.
13. [P1][Pending] `88-backfill-primary-goal-when-empty-after-initial-turn.md`.
14. [P1][Pending] `89-add-storylet-effects-contract-and-server-application.md`.
15. [P0][Complete] `90-add-startup-setup-modal-for-missing-api-key-or-model.md`.
16. [P0][Complete] `91-retrigger-setup-modal-after-dev-hard-reset-when-env-is-incomplete.md`.
17. [P1][Complete] `92-add-global-settings-menu-for-model-key-and-runtime-toggles.md`.

Duplicate/fit mapping from latest intake dump:

1. Queryable world-memory fact layer -> covered by major `52`.
2. Event-sourced projection hardening -> covered by major `53`.
3. Freeform grounding and constraints -> covered by major `54`.
4. Sparse runtime synthesis as stubs-first supply -> covered by major `55`.
5. Goal/arc as first-class lens -> covered by major `56`.
6. Staged intent/validate/narrate lane separation -> already implemented in archived major `44`; further hardening in major `54`.

## Recommended Execution Order

1. Minors `71` -> `72` -> `73` -> `74` -> `75` are complete.
2. Minor `65` is implemented and currently in `verify` pending unrelated global test-baseline failures.
3. Minors `90` -> `91` -> `92` are complete, closing fresh-start setup friction and adding settings controls.
4. Start major `52` -> `53` -> `54` as the world-memory/fact-grounding hardening spine.
5. Execute major `55` + `56` to align sparse runtime supply with goal/arc continuity.
6. Execute major `59` to enforce one authoritative reducer/rulebook across mutation paths.
7. Execute major `60`, then `61`, to standardize turn simulation and orchestration flow.
8. Execute major `57` + `58` for concurrency and transaction-safety hardening.
9. Run minors `85` -> `86` -> `87` -> `88` -> `89` as reducer-aligned hardening slices.
10. Run minors `76` -> `77` -> `78` -> `80` for runtime quality guardrails.
11. Run minors `79`, `83`, and `82` for exposure safety and operator docs.
12. Run minor `84`, then `81` audit to verify archived closures and reopen leaks.
13. Start major `50` phase 1 baseline bucketization, then staged remediation batches.
14. Re-rank queue weekly using observability triage and pruning evidence.

## Notes

- Completed history is in archive (`46` major docs and `66` minor docs); keep this active roadmap focused on pending work only.
- When an item is complete, move it to archive and update this roadmap in the same PR.
- Use `improvements/harness/06-OBSERVABILITY_AND_BOTTLENECKS.md` for weekly A/B/C bottleneck classification and reprioritization.
- Current baseline: `python scripts/dev.py verify` passes; repo-wide lint remains tracked non-blocking debt.
