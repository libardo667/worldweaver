# Prune Backlog (Staged)

Backlog items are provisional until global decision criteria are finalized.

## Wave 0: Baseline and Safety
- [x] Freeze baseline quality evidence (`quality-strict` + key smoke flows).
- [ ] Capture current flaky test list with reproducibility notes.
- [ ] Snapshot active feature flags and defaults for rollback safety.

## Wave 1: Low-Risk Structural Cleanup
- [x] Classify generated artifacts and caches (`.pytest_cache`, `.ruff_cache`, root test logs).
- [x] Separate dependency/vendor weight (`client/node_modules`) from source-of-truth inventory.
- [x] Resolve unclassified inventory entries.
- [ ] Normalize what should be tracked vs regenerated in local/dev workflows.

## Wave 2: Runtime Path Inventory
- [x] Map endpoint critical paths (`/api/next`, `/api/action`, `/api/turn`, maintenance endpoints).
- [ ] Identify duplicated orchestration logic and fallback chains.
- [ ] Identify files with no runtime/test reachability evidence.

## Wave 3: Candidate Scoring and Triage
- [ ] Score all candidates with playbook dimensions.
- [ ] Assign strategy per candidate (`delete`, `merge`, `demote`, `isolate`).
- [ ] Produce reviewed decision set before broad edits.

## Wave 4: Execution Batches
- [ ] Low-risk deletions/archivals first.
- [ ] Medium-risk merges/demotions with temporary flags where needed.
- [ ] High-risk isolates only after wave-level quality gates pass.

## Hold Point
Do not finalize broad scoring thresholds or mass-delete criteria until explicit user sign-off on assessment policy.

## New Artifacts (Additive)
- `BUCKET_INVENTORY.csv`
- `BUCKET_SUMMARY.csv`
- `SOURCE_OF_TRUTH_POLICY.md`
- `UNCLASSIFIED_RESOLUTION.md`
- `DECISION_CRITERIA_MATRIX.md` (draft)
- `CANDIDATE_SHORTLIST.md` (draft)
- `SCORING_WORKSHEET.csv` (draft)
