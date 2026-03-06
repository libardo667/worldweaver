# Batch B Frontend Source Slice 14

Date: `2026-03-06`
Status: `completed`

## Scope
- Continue `frontend_source` simplification by making prefetch state caching projection-aware at the session-store seam.
- Add optional prefetch budget metadata plumbing without changing default UI/runtime behavior when metadata is absent.

## Changes
1. Added projection-aware prefetch cache helpers in `client/src/state/sessionStore.ts`:
- introduced `PrefetchCacheScope` (`sessionId` + optional `projectionRef`)
- added scoped load/save helpers:
  - `loadPrefetchStatusCache(...)`
  - `savePrefetchStatusCache(...)`
  - `loadPrefetchBudgetCache(...)`
  - `savePrefetchBudgetCache(...)`
  - `clearPrefetchBudgetCache(...)`
- updated `clearSessionStorage()` to clear scoped prefetch cache prefixes.

2. Refactored `client/src/hooks/usePrefetchFrontier.ts`:
- added optional `projectionRef` input.
- added scoped cache hydration on hook reset/session change.
- normalized optional budget metadata from prefetch status payloads (`budget_ms`, `max_nodes`, `expansion_depth`), supporting both top-level and nested `budget` shape.
- persisted scoped status/budget snapshots via `sessionStore` and cleared scoped budget cache when metadata is absent.

3. Wired projection context propagation through turn orchestration:
- `client/src/hooks/useTurnOrchestration.ts` now supports optional `onV3TurnMetadata(...)` callback and emits metadata for:
  - `fetchScene(...)`
  - `handleChoice(...)`
  - `handleAction(...)`
  - `handleMove(...)`
- `client/src/App.tsx` now tracks `latestProjectionRef` from v3 metadata and passes it to `usePrefetchFrontier(...)`.
- `client/src/App.tsx` now updates projection context for constellation jumps via `parseV3TurnMetadata(...)`.

4. Added budget seam to topbar runtime status derivation:
- `client/src/types.ts` now includes `PrefetchBudgetMetadata`.
- `client/src/app/appHelpers.ts` `buildTopbarRuntimeStatus(...)` now accepts `prefetchBudget`, using it as an explicit "budget off" signal when metadata indicates disabled budgets.

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict` (first run hit one preexisting full-suite transient API-node failure)
- `1..3 | ForEach-Object { pytest tests/api/test_game_endpoints.py::TestGameEndpoints::test_session_bootstrap_purges_prior_same_session_state_and_prefetch -q }`
- `pytest tests/api/test_game_endpoints.py::TestGameEndpoints::test_session_bootstrap_purges_prior_same_session_state_and_prefetch -q`
- `python scripts/dev.py quality-strict` (rerun)

Results:
- frontend build: pass
- isolated transient-node reruns: pass (`4/4`)
- strict gate rerun: pass (`590 passed`)

## Batch B Impact
- Prefetch cache lifecycle is now explicitly scoped for projection lineage evolution instead of implicit session-only assumptions.
- Added stable seams for future v3 projection/budget policy work without changing current default runtime contracts.
