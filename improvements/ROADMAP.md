# Roadmap

## Current State

- Product status: Explore, Reflect, and Constellation debug modes are shipped; onboarding/bootstrap alignment and narrative evaluation harness are integrated.
- Architecture status: Behavior-preserving refactor is complete through major `37`; compass/spatial optional-assistive demotion close-out (`47`, `66`, `68`) and naming cleanup (`49`) are complete and archived.
- Top risks:
  - Class A latency/cost variability remains in runtime LLM paths; metrics surface closure is still pending in minor `44`.
  - Class C UX completeness risk is now concentrated in minor `65` (constellation graph view parity for debug usability).
  - Class B static hygiene debt remains high: `ruff` repo-scope check is still red (121 violations) and `black --check` reports 27 files to reformat.
  - Local developer runtime still lacks full single-command containerized orchestration until major `46` closes.

## Guardrails

1. No API route/path/payload shape changes unless explicitly approved.
2. Keep API layers thin (routing/validation only) and consolidate logic in services.
3. Prefer delete/merge/demote/isolate over new abstraction growth when pruning.
4. Keep lane file boundaries and contract ownership explicit before implementation.
5. Run required gates per item and final integration gates: `python -m pytest -q` and `npm --prefix client run build`.
6. Track repo-wide lint as debt (`python scripts/dev.py lint --all`) but keep it non-blocking until major `50` is complete.
7. Record evidence, unresolved risk, and rollback notes for every major/minor closure.

## Major Queue

1. [P1][Pending] `46-operationalize-dev-runtime-with-compose-and-tasks.md` (deliver canonical single-command runtime path while preserving manual fallback).
2. [P2][Deferred Non-Blocking] `50-establish-full-project-lint-baseline-and-ci-gates.md` (execute staged lint debt burn-down, then re-enable strict Gate 3 enforcement).

## Minor Queue

1. [P1][Pending/Partial] `44-add-llm-latency-and-token-usage-metrics.md` (timings exist; endpoint/aggregate closure still pending).
2. [P1][Pending] `65-add-constellation-graph-view-v1.md`.

## Recommended Execution Order

1. Complete remaining scope for minor `44` (LLM latency/token aggregate/debug surface).
2. Execute major `46` runtime orchestration work (compose/task/happy path) with fallback flow preserved.
3. Execute minor `65` constellation graph view after runtime/tooling stabilization.
4. Start major `50` phase 1 baseline bucketization, then staged remediation batches.
5. Re-rank queue weekly using observability triage and pruning evidence.

## Notes

- Completed history is in archive (`45` major docs and `65` minor docs); keep this active roadmap focused on pending work only.
- When an item is complete, move it to archive and update this roadmap in the same PR.
- Use `improvements/harness/06-OBSERVABILITY_AND_BOTTLENECKS.md` for weekly A/B/C bottleneck classification and reprioritization.
- Current baseline: `python scripts/dev.py verify` passes; repo-wide lint remains tracked non-blocking debt.
