# Prune Backlog (Staged)

Backlog items are provisional until global decision criteria are finalized.

## Wave 0: Baseline and Safety
- [x] Freeze baseline quality evidence (`quality-strict` + key smoke flows).
- [x] Capture current flaky test list with reproducibility notes.
- [x] Snapshot active feature flags and defaults for rollback safety.

## Wave 1: Low-Risk Structural Cleanup
- [x] Classify generated artifacts and caches (`.pytest_cache`, `.ruff_cache`, root test logs).
- [x] Separate dependency/vendor weight (`client/node_modules`) from source-of-truth inventory.
- [x] Resolve unclassified inventory entries.
- [x] Normalize what should be tracked vs regenerated in local/dev workflows.

## Wave 2: Runtime Path Inventory
- [x] Map endpoint critical paths (`/api/next`, `/api/action`, `/api/turn`, maintenance endpoints).
- [x] Identify duplicated orchestration logic and fallback chains.
- [x] Identify files with no runtime/test reachability evidence.

## Wave 3: Candidate Scoring and Triage
- [x] Score all candidates with playbook dimensions.
- [x] Assign strategy per candidate (`delete`, `merge`, `demote`, `isolate`).
- [x] Produce reviewed decision set before broad edits.
- Wave 3 output: `SCORING_WORKSHEET.csv` (all `reviewed_scored`) and `REVIEWED_DECISION_SET.md`.

## Wave 4: Execution Batches
- [x] Low-risk deletions/archivals first.
- [ ] Medium-risk merges/demotions with temporary flags where needed.
- [ ] High-risk isolates only after wave-level quality gates pass.
- Wave 4 Batch A executed via relocation to parent archive root (see `BATCH_A_RELOCATION_SUMMARY.md`).
- Lock exception: `worldweaver.db` retained in repo due active file lock; archived copy created externally.
- Wave 4 Batch B progress:
1. `runtime_api` merge: completed slices 1-4 (`BATCH_B_RUNTIME_API_SLICE_1.md` -> `BATCH_B_RUNTIME_API_SLICE_4.md`)
2. `runtime_services` simplify: slices 1-3 completed (`BATCH_B_RUNTIME_SERVICES_SLICE_1.md`, `BATCH_B_RUNTIME_SERVICES_SLICE_2.md`, `BATCH_B_RUNTIME_SERVICES_SLICE_3.md`)
3. `tests_integration` simplify: slices 1-6 completed (`BATCH_B_TESTS_INTEGRATION_SLICE_1.md`, `BATCH_B_TESTS_INTEGRATION_SLICE_2.md`, `BATCH_B_TESTS_INTEGRATION_SLICE_3.md`, `BATCH_B_TESTS_INTEGRATION_SLICE_4.md`, `BATCH_B_TESTS_INTEGRATION_SLICE_5.md`, `BATCH_B_TESTS_INTEGRATION_SLICE_6.md`)
  - Follow-up stabilization completed for cleanup node (`tests/api/test_game_endpoints.py::TestGameEndpoints::test_cleanup_removes_stale_sessions`); strict gate now passes.
4. `frontend_source` simplify: slices 1-9 completed (`BATCH_B_FRONTEND_SOURCE_SLICE_1.md`, `BATCH_B_FRONTEND_SOURCE_SLICE_2.md`, `BATCH_B_FRONTEND_SOURCE_SLICE_3.md`, `BATCH_B_FRONTEND_SOURCE_SLICE_4.md`, `BATCH_B_FRONTEND_SOURCE_SLICE_5.md`, `BATCH_B_FRONTEND_SOURCE_SLICE_6.md`, `BATCH_B_FRONTEND_SOURCE_SLICE_7.md`, `BATCH_B_FRONTEND_SOURCE_SLICE_8.md`, `BATCH_B_FRONTEND_SOURCE_SLICE_9.md`)
  - Latest strict gate pass preserved (`590 passed`); flaky-node watchlist remains active for continued burn-in.

## Hold Point
Resolved: user-approved scoring criteria are now applied in Wave 3 outputs.

## New Artifacts (Additive)
- `BUCKET_INVENTORY.csv`
- `BUCKET_SUMMARY.csv`
- `SOURCE_OF_TRUTH_POLICY.md`
- `UNCLASSIFIED_RESOLUTION.md`
- `DECISION_CRITERIA_MATRIX.md`
- `CANDIDATE_SHORTLIST.md` (superseded)
- `SCORING_WORKSHEET.csv` (reviewed)
- `FLAKY_TEST_REGISTER.md`
- `FEATURE_FLAG_SNAPSHOT.md`
- `FEATURE_FLAG_SNAPSHOT.csv`
- `V3_RUNTIME_BUDGET_SNAPSHOT.csv`
- `TRACKED_VS_REGENERATED_NORMALIZATION.md`
- `ORCHESTRATION_DUPLICATION_MAP.md`
- `REACHABILITY_EVIDENCE.csv`
- `REACHABILITY_GAPS.md`
- `REACHABILITY_METHOD.md`
- `build_reachability_evidence.py`
- `COVERAGE_SUMMARY.json`
- `COVERAGE_REPORT.txt`
- `REVIEWED_DECISION_SET.md`
- `execute_batch_a_relocation.ps1`
- `BATCH_A_RELOCATION_MANIFEST.csv`
- `BATCH_A_RELOCATION_CONSOLIDATED.csv`
- `BATCH_A_RELOCATION_SUMMARY.md`
- `BATCH_B_RUNTIME_API_SLICE_1.md`
- `BATCH_B_RUNTIME_API_SLICE_2.md`
- `BATCH_B_RUNTIME_API_SLICE_3.md`
- `BATCH_B_RUNTIME_API_SLICE_4.md`
- `BATCH_B_RUNTIME_SERVICES_SLICE_1.md`
- `BATCH_B_RUNTIME_SERVICES_SLICE_2.md`
- `BATCH_B_RUNTIME_SERVICES_SLICE_3.md`
- `BATCH_B_TESTS_INTEGRATION_SLICE_1.md`
- `BATCH_B_TESTS_INTEGRATION_SLICE_2.md`
- `BATCH_B_TESTS_INTEGRATION_SLICE_3.md`
- `BATCH_B_TESTS_INTEGRATION_SLICE_4.md`
- `BATCH_B_TESTS_INTEGRATION_SLICE_5.md`
- `BATCH_B_TESTS_INTEGRATION_SLICE_6.md`
- `BATCH_B_FRONTEND_SOURCE_SLICE_1.md`
- `BATCH_B_FRONTEND_SOURCE_SLICE_2.md`
- `BATCH_B_FRONTEND_SOURCE_SLICE_3.md`
- `BATCH_B_FRONTEND_SOURCE_SLICE_4.md`
- `BATCH_B_FRONTEND_SOURCE_SLICE_5.md`
- `BATCH_B_FRONTEND_SOURCE_SLICE_6.md`
- `BATCH_B_FRONTEND_SOURCE_SLICE_7.md`
- `BATCH_B_FRONTEND_SOURCE_SLICE_8.md`
- `BATCH_B_FRONTEND_SOURCE_SLICE_9.md`
- `V3_FOLLOW_ON_CHECKLIST.md`
