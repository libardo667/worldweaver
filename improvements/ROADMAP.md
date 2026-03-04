# Roadmap

## Current State

- Product status: Explore, Reflect, and Constellation debug modes are shipped; onboarding/bootstrap alignment and narrative evaluation harness are integrated.
- Architecture status: Behavior-preserving refactor is complete through major `37`; compass/spatial optional-assistive demotion close-out (`47`, `66`, `68`), naming cleanup (`49`), runtime LLM latency/token metrics closure (`44`), and local runtime operationalization (`46`) are complete and archived.
- Top risks:
  - Class A narrative coherence and onboarding latency: batch storylet generation produces disconnected vignettes and 30–60s waits; addressed by major `51` and minor `71`.
  - Class A latency/cost variability remains in runtime LLM paths; local observability is now present, but metrics are still in-memory/local-process only.
  - Class C UX completeness risk is now concentrated in minor `65` (constellation graph view parity for debug usability).
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

1. [P1][Pending] `51-jit-beat-generation-pipeline.md` (replace batch storylet generation with world-bible + JIT beat generation for narrative coherence and onboarding speed).
2. [P2][Deferred Non-Blocking] `50-establish-full-project-lint-baseline-and-ci-gates.md` (execute staged lint debt burn-down, then re-enable strict Gate 3 enforcement).

## Minor Queue

1. [P0][In Progress] `71-switch-default-llm-to-fluency-model.md` ✅ COMPLETE.
2. [P1][Pending] `72-add-jit-beat-generation-feature-flag.md` (safety flag for major 51 rollout).
3. [P1][Pending] `73-add-world-bible-prompt-and-generator.md` (fast world bible LLM function).
4. [P1][Pending] `74-add-jit-beat-generation-function.md` (per-turn JIT beat LLM function + prompt).
5. [P1][Pending] `75-wire-jit-pipeline-bootstrap-and-api.md` (end-to-end wiring, arc tracking).
6. [P1][Pending] `65-add-constellation-graph-view-v1.md`.

## Recommended Execution Order

1. ✅ Minor `71` — model default switch (complete).
2. Minor `72` → `73` → `74` → `75` — JIT pipeline in sequence (all on branch `major/51-jit-beat-generation-pipeline`).
3. Execute minor `65` constellation graph view after narrative pipeline stabilization.
4. Start major `50` phase 1 baseline bucketization, then staged remediation batches.
5. Re-rank queue weekly using observability triage and pruning evidence.

## Notes

- Completed history is in archive (`46` major docs and `66` minor docs); keep this active roadmap focused on pending work only.
- When an item is complete, move it to archive and update this roadmap in the same PR.
- Use `improvements/harness/06-OBSERVABILITY_AND_BOTTLENECKS.md` for weekly A/B/C bottleneck classification and reprioritization.
- Current baseline: `python scripts/dev.py verify` passes; repo-wide lint remains tracked non-blocking debt.
