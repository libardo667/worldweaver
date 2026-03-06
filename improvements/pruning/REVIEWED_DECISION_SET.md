# Reviewed Decision Set (Wave 3)

Date: `2026-03-06`  
Basis:
- `SCORING_WORKSHEET.csv` (all units `reviewed_scored`)
- `REACHABILITY_EVIDENCE.csv` (coverage-backed)
- `ORCHESTRATION_DUPLICATION_MAP.md`
- `SOURCE_OF_TRUTH_POLICY.md`

## Strategy Distribution
- `keep`: 9
- `isolate`: 6
- `simplify`: 3
- `delete`: 3
- `merge`: 1
- `demote`: 1

## Domain Decisions
1. `runtime_api` -> `merge`
2. `runtime_services` -> `simplify`
3. `runtime_models` -> `keep`
4. `runtime_core` -> `keep`
5. `runtime_entry` -> `keep`
6. `tests_api` -> `keep`
7. `tests_service` -> `keep`
8. `tests_integration` -> `simplify`
9. `tests_contract` -> `keep`
10. `frontend_source` -> `simplify`
11. `frontend_vendor` -> `isolate`
12. `frontend_build` -> `delete`
13. `playtest_runs` -> `isolate`
14. `playtest_markdown` -> `isolate`
15. `playtest_logs` -> `delete`
16. `reports_outputs` -> `isolate`
17. `local_databases` -> `isolate`
18. `local_caches` -> `delete`
19. `harness_source` -> `demote`
20. `planning_active` -> `keep`
21. `planning_archive` -> `isolate`
22. `repo_meta` -> `keep`
23. `data_assets` -> `keep`

## Execution Batches (Proposed + Live Status)

### Batch A (Low-Risk, Generated Artifacts)
- `frontend_build`, `playtest_logs`, `local_caches`
- `playtest_runs`, `playtest_markdown`, `reports_outputs`, `local_databases`
- Goal: remove/relocate generated noise first without touching runtime contracts.
- Execution status: `completed` (relocated to parent archive root).
- Evidence: `BATCH_A_RELOCATION_SUMMARY.md`, `BATCH_A_RELOCATION_CONSOLIDATED.csv`.
- Exception: `worldweaver.db` remained in repo due active file lock; archived copy exists in relocation root.

### Batch B (Medium-Risk Structural)
- `runtime_api` (`merge`), `runtime_services` (`simplify`)
- `tests_integration` (`simplify`), `frontend_source` (`simplify`)
- Goal: reduce duplicate orchestration and test/client complexity in bounded commits.
- Execution status: `in_progress`
- Track status:
1. `runtime_api`: `completed` (slices 1-4)
2. `runtime_services`: `in_progress` (slices 1-3 complete: explicit deepening gate + default-path short-circuit when improvement flags are off + adapter-only runtime-service entrypoint for auto-improvement)
3. `tests_integration`: `completed` (slices 1-6 complete: removed redundant state-manager clears + centralized API/concurrency/helper patterns + shared harness metric/record helper patterns + shared session-state/projection helper patterns + parameter-sweep module decomposition + API/harness boundary split; cleanup-node stabilization landed and strict gate passes)
4. `frontend_source`: `pending`
- Evidence:
1. `BATCH_B_RUNTIME_API_SLICE_1.md`
2. `BATCH_B_RUNTIME_API_SLICE_2.md`
3. `BATCH_B_RUNTIME_API_SLICE_3.md`
4. `BATCH_B_RUNTIME_API_SLICE_4.md`
5. `BATCH_B_RUNTIME_SERVICES_SLICE_1.md`
6. `BATCH_B_RUNTIME_SERVICES_SLICE_2.md`
7. `BATCH_B_RUNTIME_SERVICES_SLICE_3.md`
8. `BATCH_B_TESTS_INTEGRATION_SLICE_1.md`
9. `BATCH_B_TESTS_INTEGRATION_SLICE_2.md`
10. `BATCH_B_TESTS_INTEGRATION_SLICE_3.md`
11. `BATCH_B_TESTS_INTEGRATION_SLICE_4.md`
12. `BATCH_B_TESTS_INTEGRATION_SLICE_5.md`
13. `BATCH_B_TESTS_INTEGRATION_SLICE_6.md`

### Batch C (Policy/Workflow Demotion)
- `harness_source` (`demote`)
- Goal: keep tooling but detach from critical default path.

### Batch D (Keep-Only Stability Domains)
- `runtime_models`, `runtime_core`, `runtime_entry`
- `tests_api`, `tests_service`, `tests_contract`
- `planning_active`, `repo_meta`, `data_assets`
- Goal: no broad pruning; only opportunistic hygiene if evidence changes.

## Guardrails Before Batch B/C
- Re-run:
1. `python scripts/dev.py quality-strict`
2. `coverage run --source=src -m pytest tests -q`
3. targeted endpoint smoke (`/api/next`, `/api/action`, `/api/turn` if enabled)
- Preserve rollback notes per commit.
- No reducer-contract breakage without explicit approval.
