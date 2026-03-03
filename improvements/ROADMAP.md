# Roadmap

## Current State

- Product status: Explore, Reflect, and Constellation debug modes are shipped; onboarding/bootstrap alignment and narrative evaluation harness are integrated.
- Architecture status: Behavior-preserving refactor is complete through major `37`; pruning cycle `001` integrated major compass/spatial demotion slices and compatibility cleanup.
- Top risks:
  - Class A latency/cost variability remains in runtime LLM paths; metrics surface closure is still pending in minor `44`.
  - Class C correctness/UX risk remains around final compass demotion close-out and compatibility coupling at package-import boundaries.
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

1. [P0][In Progress] `47-demote-compass-to-optional-assistive-navigation-layer.md` (close remaining acceptance and finalize feature-control posture).
2. [P1][Pending] `46-operationalize-dev-runtime-with-compose-and-tasks.md` (deliver canonical single-command runtime path while preserving manual fallback).
3. [P2][Deferred Non-Blocking] `50-establish-full-project-lint-baseline-and-ci-gates.md` (execute staged lint debt burn-down, then re-enable strict Gate 3 enforcement).

## Minor Queue

1. [P0][Close-Out] `49-rename-fastapi-title-to-worldweaver-backend.md`.
2. [P0][Close-Out] `66-compass-redaction-for-inaccessible-moves.md`.
3. [P0][Close-Out] `68-make-place-panel-refresh-best-effort-after-turn-render.md`.
4. [P1][Pending] `65-add-constellation-graph-view-v1.md`.
5. [P1][Close-Out Candidate] `42-add-world-projection-backfill-command.md` (implementation present; acceptance/archive pass pending).
6. [P1][Close-Out Candidate] `43-add-session-bootstrap-endpoint-with-goal.md` (endpoint present; acceptance/archive pass pending).
7. [P1][Close-Out Candidate] `46-add-refactor-phase-test-gate-checklist.md` (checklist exists; evidence fill + archive pending).
8. [P1][Pending/Partial] `44-add-llm-latency-and-token-usage-metrics.md` (timings exist; endpoint/aggregate closure still pending).

## Recommended Execution Order

1. Close minors `66` and `68` with explicit acceptance verification and archive updates.
2. Close major `47` end-to-end after confirming compass optionality and non-blocking spatial refresh behavior.
3. Execute minor `49` (FastAPI title rename) and verify no contract/path regressions.
4. Run close-out sweep for minors `42`, `43`, and `46` (verify criteria, archive, remove from active queue).
5. Complete remaining scope for minor `44` (LLM latency/token aggregate/debug surface).
6. Execute major `46` runtime orchestration work (compose/task/happy path) with fallback flow preserved.
7. Execute minor `65` constellation graph view after runtime/tooling stabilization.
8. Start major `50` phase 1 baseline bucketization, then staged remediation batches.
9. Re-rank queue weekly using observability triage and pruning evidence.

## Notes

- Completed history is in archive (`44` major docs and `59` minor docs); keep this active roadmap focused on pending or close-out work only.
- When an item is complete, move it to archive and update this roadmap in the same PR.
- Use `improvements/harness/06-OBSERVABILITY_AND_BOTTLENECKS.md` for weekly A/B/C bottleneck classification and reprioritization.
- Current baseline: `python scripts/dev.py verify` passes; repo-wide lint remains tracked non-blocking debt.
