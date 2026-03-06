# Pruning Retrospective (2026-03-06)

## Scope
- Retrospective for the full pruning run tracked under `improvements/pruning`.
- Source set reviewed: all pruning markdown artifacts plus the canonical pruning evidence tables.

## Inputs Reviewed
- Markdown planning/evidence docs reviewed: `49` files (all `*.md` under `improvements/pruning` before archival).
- Inventory evidence:
  - `FILE_INVENTORY.csv`: `3732` rows
  - `BUCKET_INVENTORY.csv`: `3732` rows
  - `BUCKET_SUMMARY.csv`: `16` rows
  - `REACHABILITY_EVIDENCE.csv`: `53` rows
- Decision evidence:
  - `SCORING_WORKSHEET.csv`: `23` reviewed units
  - strategy distribution: `keep 9`, `isolate 6`, `simplify 3`, `delete 3`, `merge 1`, `demote 1`

## Execution Summary

### Wave 0-3 Outcomes
- Wave 0 established baseline quality, flaky test register, and feature-flag snapshots.
- Wave 1 established source-of-truth and regenerated-artifact boundaries.
- Wave 2 mapped runtime critical paths and duplication/fallback chains.
- Wave 3 completed scoring and produced reviewed execution strategy.

### Wave 4 Outcomes
- Batch A completed generated-artifact relocation with manifested evidence.
- Batch B completed all planned medium-risk structural slices:
  - runtime API merge: `4` slices complete
  - runtime services simplify: `3` slices complete
  - tests integration simplify: `6` slices complete
  - frontend source simplify: `16` slices complete
- Batch C completed harness demotion:
  - optional harness/eval workflows moved under `python scripts/dev.py harness ...`
  - legacy aliases retained with warning + compatibility pass-through
- High-risk isolates explicitly deferred:
  - decision state: `deferred_until_v3_alpha`
  - deferred domains: `frontend_vendor`, `planning_archive`
  - re-entry criteria: v3 alpha scaffold + two consecutive `quality-strict` passes on v3 branch

## Guardrail and Stability Readout
- Latest strict gate evidence in this run: `python scripts/dev.py quality-strict` passing with `590 passed` and warning budget unchanged.
- Known residual risk pattern: transient flaky nodes were documented and tracked; no unresolved blocker remained in the pruning closure path.

## What Improved
- Runtime and service orchestration surface is less duplicated and easier to reason about.
- Integration test surface is less repetitive and better normalized around shared helpers.
- Frontend mode/lane wiring was decomposed into explicit contracts and routing seams.
- Harness workflows are now demoted from the primary validation path, reducing accidental coupling.

## What Was Intentionally Deferred
- High-risk isolate moves with limited immediate v3 leverage were deferred to preserve implementation momentum and avoid avoidable path/tooling breakage during v3 startup.

## Final Archive Action (2026-03-06)
- Archived all pruning markdown planning docs from `improvements/pruning` into:
  - `improvements/history/pruning_run_2026-03-06/`
- Archived run-specific non-markdown evidence artifacts (`.csv`, `.json`, `.xml`, `.txt`) into:
  - `improvements/history/pruning_run_2026-03-06/evidence/`
- Kept reusable pruning automation in `improvements/pruning`:
  - `build_reachability_evidence.py`
  - `execute_batch_a_relocation.ps1`

## Suggested Hand-off
- Treat pruning wave as closed for implementation purposes.
- Start v3 execution from `VISION.md` and `ROADMAP.md` with deferred isolate criteria as the only pruning re-entry gate.
