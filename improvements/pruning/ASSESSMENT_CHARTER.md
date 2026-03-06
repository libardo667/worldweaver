# WorldWeaver Repository Assessment Charter

## Objective
Perform a comprehensive, staged assessment of the entire `worldweaver` directory and classify every file as:
- core runtime
- test-critical
- ops-critical
- supporting
- archive
- delete candidate

The output must be evidence-driven and safe to execute in bounded pruning waves.

## Scope
- Included: all files under repository root (runtime, tests, harness, docs, artifacts, tooling, data snapshots).
- Excluded from direct deletion without explicit sign-off: canonical production runtime paths and route contracts.

## Hard Constraints
- No breaking API contract changes without explicit approval.
- Reducer remains canonical world-state authority.
- Pruning changes must be reversible in bounded commits.
- Every medium/high-risk change requires rollback notes.

## Deliverables
- `FILE_INVENTORY.csv`: machine-readable full-file census and classification columns.
- `INVENTORY_SUMMARY.md`: high-level counts, hotspots, obvious noise.
- `DECISION_LOG.md`: file-level keep/merge/archive/delete decisions with evidence.
- `PRUNE_BACKLOG.md`: execution queue by risk wave and strategy.

## Staged Plan
1. Plan-of-plan and repository census.
2. Runtime critical-path mapping (endpoint -> service -> model -> side effects).
3. Baseline freeze (tests, quality gates, latency/error snapshots).
4. Reachability and duplication evidence pass.
5. File-by-file triage and scoring.
6. Code-block-level simplification in high-leverage files only.
7. Pruning execution waves (low -> medium -> high risk).
8. Regression and gate validation after each wave.
9. Consolidation and temporary-flag cleanup.
10. Ongoing hygiene rules in CI/process.

## Decision-Criteria Hold
Broader scoring policy and thresholds are intentionally not finalized yet.

Before finalizing global criteria, align on:
- what counts as "core" vs "supporting" for this cycle
- how aggressively to prune playtest artifacts and local tooling residue
- whether frontend and harness are in-scope for this pass or sequenced later

## Current Status
- Stage 0 started.
- Stage 1 census artifact generated: `FILE_INVENTORY.csv`.
- Stage 2 runtime critical-path map generated: `CRITICAL_PATH_MAP.md`.
- Stage 3 baseline freeze evidence captured: `BASELINE_FREEZE.md`.
- Stage 4 evidence pass captured:
- flaky register (`FLAKY_TEST_REGISTER.md`)
- feature/runtime flag snapshots (`FEATURE_FLAG_SNAPSHOT.md`, `FEATURE_FLAG_SNAPSHOT.csv`, `V3_RUNTIME_BUDGET_SNAPSHOT.csv`)
- orchestration duplication/fallback map (`ORCHESTRATION_DUPLICATION_MAP.md`)
- reachability evidence and gap summary (`REACHABILITY_EVIDENCE.csv`, `REACHABILITY_GAPS.md`) now coverage-backed (`COVERAGE_SUMMARY.json`, `REACHABILITY_METHOD.md`)
- Source-of-truth vs generated/dependency bucket inventory generated (`BUCKET_INVENTORY.csv`, `BUCKET_SUMMARY.csv`).
- Draft criteria and shortlist generated (`DECISION_CRITERIA_MATRIX.md`, `CANDIDATE_SHORTLIST.md`).
- Source-of-truth boundary policy documented (`SOURCE_OF_TRUTH_POLICY.md`).
- Tracked vs regenerated normalization policy added (`TRACKED_VS_REGENERATED_NORMALIZATION.md`).
- Wave 3 scoring completed (`SCORING_WORKSHEET.csv`, all units `reviewed_scored`).
- Reviewed decision set produced (`REVIEWED_DECISION_SET.md`).
- Wave 4 Batch A executed:
- low-risk generated artifacts relocated to parent workspace archive
- execution manifests captured (`BATCH_A_RELOCATION_SUMMARY.md`, `BATCH_A_RELOCATION_CONSOLIDATED.csv`, `BATCH_A_RELOCATION_MANIFEST.csv`)
- Unclassified inventory entries resolved (`UNCLASSIFIED_RESOLUTION.md`).
