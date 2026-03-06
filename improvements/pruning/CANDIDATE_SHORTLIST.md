# First-Pass Candidate Shortlist By Bucket (Draft)

Status: `proposed`  
Scope: additive planning only. No prune operations executed here.

Data source:
- [BUCKET_SUMMARY.csv](C:/Users/levib/PythonProjects/worldweaver/worldweaver/improvements/pruning/BUCKET_SUMMARY.csv)
- [BUCKET_INVENTORY.csv](C:/Users/levib/PythonProjects/worldweaver/worldweaver/improvements/pruning/BUCKET_INVENTORY.csv)

## Bucket Snapshot
- `generated_dependency_vendor_local`: 2541 files, 65.91 MB
- `generated_playtest_artifact_relocate`: 460 files, 8.51 MB
- `planning_archive_history`: 199 files, 0.42 MB
- `source_tests`: 178 files, 2.07 MB
- `source_runtime_tooling`: 108 files, 0.94 MB
- `generated_cache_local`: 87 files, 0.89 MB
- `source_frontend`: 45 files, 0.27 MB
- `planning_active_docs`: 39 files, 0.06 MB
- `report_output_artifact_relocate`: 24 files, 1.08 MB
- `source_harness_tooling`: 15 files, 0.39 MB
- `generated_log_artifact_relocate`: 15 files, 0.08 MB
- `repo_meta_docs`: 9 files, 0.02 MB
- `data_asset`: 5 files, 0.08 MB
- `local_db_artifact_relocate`: 3 files, 2.86 MB
- `generated_build_output_local`: 3 files, 0.22 MB
- `local_secret_env_local`: 1 file

## Proposed Priority Queue (Draft)
1. P0: classify and separate generated/dependency bulk from source-of-truth scope.
2. P1: resolve unclassified files and lock source-of-truth boundaries.
3. P2: score runtime and tests paths for simplify/merge opportunities.
4. P3: archive/history/docs cleanup after runtime boundary is stable.

## P0 Candidates (Likely Low-Risk Structural)
- `generated_dependency_vendor_local` (`client/node_modules/*`)
  - Proposed strategy: classify as generated local dependency state; keep in-place for tooling compatibility.
- `generated_cache_local` (`.pytest_cache`, `.ruff_cache`, `__pycache__`)
  - Proposed strategy: remove from prune-scoring scope as generated local state.
- `generated_log_artifact_relocate` and `report_output_artifact_relocate`
  - Proposed strategy: relocate to parent artifact retention area.
- `generated_build_output_local` (`client/dist/*`)
  - Proposed strategy: classify as generated local build output.
- `local_db_artifact_relocate` (`worldweaver.db`, `test_database.db`, `test_env_integration.db`)
  - Proposed strategy: relocate DB snapshots to parent artifact area.

## P1 Candidates (Boundary Clarification)
- `unclassified_review` now `0`
  - Resolution captured in `UNCLASSIFIED_RESOLUTION.md`.
  - Proposed strategy: keep bucket clean at zero in each future inventory refresh.
- `planning_archive_history` (199 files)
  - Proposed strategy: keep archived but reduce noise in active assessment scope.

## P2 Candidates (Core Code Simplify/Merge Review)
- Runtime ingress overlap:
  - `/api/next`, `/api/action`, `/api/turn` all route through `TurnOrchestrator`.
  - Proposed strategy: identify duplicate endpoint-layer orchestration and observability wrappers.
- Session/state maintenance concentration:
  - `src/api/game/state.py` has broad responsibilities (bootstrap, cleanup, reset, diagnostics, cache clearing).
  - Proposed strategy: score for decomposition opportunities (after policy sign-off).
- Prefetch/projection cross-cutting:
  - `prefetch_service`, `storylet_selector`, `turn_service` interaction points.
  - Proposed strategy: identify duplicated budget/flag checks and path coupling.

## Hold Points Before Pruning
- Final criteria matrix sign-off.
- Explicit policy on artifact retention in-repo.
- Confirmation of in-scope domains for this cycle (backend-only vs full repo).
