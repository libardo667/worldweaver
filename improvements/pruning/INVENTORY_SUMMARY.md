# Inventory Summary (Initial Census)

## Snapshot
- Total files in repository tree (including `.git`): `6796`
- Total assessable files in inventory (excluding `.git` internals): `3732`
- Source: recursive file census across repository root

## Counts By Category
- `frontend`: 2589
- `playtest_artifacts`: 463
- `planning_docs`: 238
- `tests`: 177
- `runtime`: 122
- `misc`: 38
- `reports`: 29
- `cache`: 26
- `migrations`: 18
- `tooling`: 16
- `harness`: 13
- `data`: 3

## Top-Level Hotspots
- `client`: 2589
- `playtests`: 463
- `improvements`: 238
- `tests`: 177
- `src`: 122

## Early Signals (Non-Final)
- The repository contains substantial local/dependency weight under `client/` (including `node_modules` binaries).
- `playtests/` contains many run artifacts that are likely high-volume, low-runtime-value for core backend operation.
- Runtime backend surface (`src/`) is comparatively small, making code-block-level pruning feasible after inventory triage.
- There are cache and local log residue files in repo root and tooling caches that should likely be formalized as generated/ignored artifacts.

## Next Step
Stage 2 and Stage 3 artifacts are now in place (`CRITICAL_PATH_MAP.md`, `BASELINE_FREEZE.md`).
Source-of-truth policy and bucketed inventory pass are now in place (`SOURCE_OF_TRUTH_POLICY.md`, `BUCKET_SUMMARY.csv`).
Stage 4 evidence pass is now in place (`FLAKY_TEST_REGISTER.md`, `FEATURE_FLAG_SNAPSHOT.md`, `ORCHESTRATION_DUPLICATION_MAP.md`, `REACHABILITY_GAPS.md`) with coverage-backed reachability artifacts (`COVERAGE_SUMMARY.json`, `REACHABILITY_METHOD.md`).
Wave 3 scoring and strategy assignment are complete for all worksheet units (`SCORING_WORKSHEET.csv`).
Wave 4 Batch A is executed with generated artifact relocation to parent workspace archive (`BATCH_A_RELOCATION_SUMMARY.md`).
Wave 4 Batch B is in progress:
1. `runtime_api` merge slices are complete (`BATCH_B_RUNTIME_API_SLICE_1.md` through `BATCH_B_RUNTIME_API_SLICE_4.md`).
2. `runtime_services` simplify has completed three slices:
- explicit deepening flag control (`BATCH_B_RUNTIME_SERVICES_SLICE_1.md`)
- disabled-path short-circuit for auto-improvement (`BATCH_B_RUNTIME_SERVICES_SLICE_2.md`)
- adapter-only runtime-service entrypoint for auto-improvement (`BATCH_B_RUNTIME_SERVICES_SLICE_3.md`)
3. `tests_integration` simplify has started with slice 1:
- removed redundant state-manager clears and normalized API-success assertions (`BATCH_B_TESTS_INTEGRATION_SLICE_1.md`)
4. `tests_integration` simplify expanded in slice 2:
- added shared integration helper module and refactored multiple integration tests to use centralized API/concurrency assertions (`BATCH_B_TESTS_INTEGRATION_SLICE_2.md`)
5. `tests_integration` simplify expanded in slice 3:
- added shared harness integration helper module and refactored harness-heavy integration tests to use centralized metric/record helper patterns (`BATCH_B_TESTS_INTEGRATION_SLICE_3.md`)
6. `tests_integration` simplify expanded in slice 4:
- added shared session-state integration helper module and refactored session-persistence/simulation tests to use centralized state/projection helper patterns (`BATCH_B_TESTS_INTEGRATION_SLICE_4.md`)
7. `tests_integration` simplify expanded in slice 5:
- decomposed the largest remaining parameter-sweep integration module into focused test files and extended shared harness builders/assertion helpers (`BATCH_B_TESTS_INTEGRATION_SLICE_5.md`)
8. `tests_integration` simplify expanded in slice 6:
- split API turn-progression integration from harness utility coverage; added helper-driven subprocess/nested assertion patterns and parametrized spatial movement checks (`BATCH_B_TESTS_INTEGRATION_SLICE_6.md`)
- quality-strict re-run note: cleanup node stabilization landed (`tests/api/test_game_endpoints.py::TestGameEndpoints::test_cleanup_removes_stale_sessions`); full strict gate now passes.
9. `frontend_source` simplify started in slice 1:
- extracted App runtime/config helper block into `client/src/app/appHelpers.ts` and reduced `App.tsx` monolith scope (`BATCH_B_FRONTEND_SOURCE_SLICE_1.md`)
- frontend build and full strict gate pass preserved.
10. `frontend_source` simplify expanded in slice 2:
- extracted topbar/mode shell JSX from `App.tsx` into `client/src/components/AppTopbar.tsx` (`BATCH_B_FRONTEND_SOURCE_SLICE_2.md`)
- frontend build pass preserved; strict reruns hit preexisting API flaky nodes, each passing in isolated reruns.
11. `frontend_source` simplify expanded in slice 3:
- extracted Explore center-column composition from `App.tsx` into `client/src/components/ExploreCenterColumn.tsx` (`BATCH_B_FRONTEND_SOURCE_SLICE_3.md`)
- frontend build and strict gate pass preserved (`590 passed`).
12. `frontend_source` simplify expanded in slice 4:
- extracted Explore-mode routing branch from `App.tsx` into `client/src/components/ExploreMode.tsx` (`BATCH_B_FRONTEND_SOURCE_SLICE_4.md`)
- frontend build and strict gate pass preserved (`590 passed`).
13. `frontend_source` simplify expanded in slice 5:
- unified replacement-session local-state reset wiring between `handleResetSession()` and `handleDevHardReset()` via shared helper in `App.tsx` (`BATCH_B_FRONTEND_SOURCE_SLICE_5.md`)
- frontend build and strict gate pass preserved (`590 passed`).
14. `frontend_source` simplify expanded in slice 6:
- centralized repeated turn-lifecycle begin/end state wiring with shared helpers in `App.tsx` (`BATCH_B_FRONTEND_SOURCE_SLICE_6.md`)
- frontend build and strict gate pass preserved (`590 passed`).
15. `frontend_source` simplify expanded in slice 7:
- extracted turn orchestration (`choice/action/move` + scene fetch/post-turn refresh) into `client/src/hooks/useTurnOrchestration.ts` and added narrator-lane stubs in `client/src/app/v3NarratorStubs.ts` (`BATCH_B_FRONTEND_SOURCE_SLICE_7.md`)
- strict gate had one transient failure in full-suite context, then passed on rerun (`590 passed`).
16. `frontend_source` simplify expanded in slice 8:
- refactored narrator seam into explicit world/scene/player lane adapters and moved scene-lane default notices out of turn orchestration internals (`BATCH_B_FRONTEND_SOURCE_SLICE_8.md`)
- frontend build and strict gate pass preserved (`590 passed`).
17. `frontend_source` simplify expanded in slice 9:
- split Explore center rendering into explicit `SceneLanePanel` and `PlayerHintPanel` boundaries and grouped lane props in `ExploreMode` (`BATCH_B_FRONTEND_SOURCE_SLICE_9.md`)
- frontend build and strict gate pass preserved (`590 passed`).
18. `frontend_source` simplify expanded in slice 10:
- centralized topbar runtime status derivation into typed helper model and added feature-flagged lane/budget chips (`BATCH_B_FRONTEND_SOURCE_SLICE_10.md`)
- frontend build and strict gate pass preserved (`590 passed`).
19. `frontend_source` simplify expanded in slice 11:
- formalized typed v3 response metadata shapes and centralized parser wiring for `projection_ref`, `clarity_level`, and `lane_source` (`BATCH_B_FRONTEND_SOURCE_SLICE_11.md`)
- frontend build and strict gate pass preserved (`590 passed`).
20. `frontend_source` simplify expanded in slice 12:
- extracted session lifecycle flows (`onboarding`, `session reset`, `dev hard reset`) into `client/src/hooks/useSessionLifecycle.ts` with explicit thread/world cache invalidation seams (`BATCH_B_FRONTEND_SOURCE_SLICE_12.md`)
- frontend build and strict gate pass preserved (`590 passed`).
21. `frontend_source` simplify expanded in slice 13:
- replaced App mode conditional render chain with typed `ModeRouter` payload contract and exported mode-view prop types for explicit routing boundaries (`BATCH_B_FRONTEND_SOURCE_SLICE_13.md`)
- frontend build and strict gate pass preserved (`590 passed`).
22. `frontend_source` simplify expanded in slice 14:
- added projection-scoped prefetch status/budget cache helpers in `sessionStore`, wired metadata-aware cache read/write flow in `usePrefetchFrontier`, and propagated latest projection refs from turn metadata through App/hook seams (`BATCH_B_FRONTEND_SOURCE_SLICE_14.md`)
- frontend build passed; strict gate rerun passed (`590 passed`) after one transient full-suite API-node failure that passed isolated reruns.
23. `frontend_source` simplify expanded in slice 15:
- extracted mode payload assembly from `App.tsx` into `client/src/hooks/useModeRouterPayload.ts` with typed onboarding/memory/lane schema groupings (`BATCH_B_FRONTEND_SOURCE_SLICE_15.md`)
- frontend build and strict gate pass preserved (`590 passed`).
24. `frontend_source` simplify expanded in slice 16:
- introduced shared mode-level `ExploreModePayload` contracts + normalization (`client/src/components/exploreModePayload.ts`) and routed Explore mode payload via normalized contract shape instead of view-internal flat props (`BATCH_B_FRONTEND_SOURCE_SLICE_16.md`)
- frontend build and strict gate pass preserved (`590 passed`).
Wave 4 Batch B status is now complete across `runtime_api`, `runtime_services`, `tests_integration`, and `frontend_source`.
Current next step is Wave 4 Batch C (`harness_source` demotion) per `REVIEWED_DECISION_SET.md`.
