# Pruning Coordination Plan (2026-03-03)

## Scope
This plan is based on:
- `improvements/VISION.md`
- `improvements/ROADMAP.md`
- `improvements/harness/07-PRUNING_PLAYBOOK.md`
- `improvements/harness/03-AGENT_EXECUTION_PROTOCOL.md`
- `improvements/majors/MAJOR_SCHEMA.md`
- `improvements/minors/MINOR_SCHEMA.md`

Scoring scale is `1-5` (`1 = low`, `5 = high`).

## Top 8 Pruning Candidates
| Rank | Candidate | Primary files/signals | User value | Reliability | Complexity cost | Risk | Recommended action |
|---|---|---|---:|---:|---:|---:|---|
| 1 | Compass as a turn-critical dependency | `client/src/App.tsx` turn flow depends on `refreshPlace()` and compass/spatial freshness | 2 | 2 | 5 | 4 | `demote` |
| 2 | Spatial refresh blocks post-turn completion quality | `client/src/App.tsx` uses `Promise.all([refreshMemory, refreshPlace])` in turn paths | 2 | 2 | 4 | 4 | `isolate` |
| 3 | Direction affordance mismatch (adjacency vs traversability) | `client/src/components/Compass.tsx`, `client/src/hooks/useKeyboardNavigation.ts`, `src/api/game/spatial.py` | 3 | 2 | 4 | 3 | `merge` |
| 4 | Runtime spatial auto-fixer mutates authored content | `src/services/story_smoother.py`, `src/services/auto_improvement.py`, ingest trigger path | 2 | 2 | 5 | 5 | `demote` |
| 5 | Compatibility re-export layers from refactor transition | `src/api/game/__init__.py`, `src/api/author/__init__.py`, `save_storylets_with_postprocessing()` alias | 1 | 3 | 4 | 2 | `delete` |
| 6 | Legacy `set_vars` compatibility branches in runtime navigation | `src/services/spatial_navigator.py` choice parsing supports `set` and `set_vars` repeatedly | 1 | 3 | 4 | 3 | `merge` |
| 7 | Legacy seeding path exposed in public reset flow | `src/api/game/state.py`, `src/services/seed_data.py`, `settings.enable_legacy_test_seeds` | 2 | 3 | 3 | 4 | `isolate` |
| 8 | Full-repo lint gate as hard merge blocker before debt burn-down | `improvements/majors/50...`, `scripts/dev.py`, CI/docs gate surface | 3 | 4 | 5 | 3 | `demote` |

## Agent Lanes (Non-Overlapping Boundaries)
### Lane 1: Client Navigation Demotion
Focus:
- Candidates `1`, `2`, client side of `3`.

Allowed files:
- `client/src/App.tsx`
- `client/src/components/Compass.tsx`
- `client/src/components/PlacePanel.tsx`
- `client/src/hooks/useKeyboardNavigation.ts`
- `client/src/hooks/usePrefetchFrontier.ts`
- `client/src/types.ts`
- `client/src/styles.css`

### Lane 2: Spatial/Prefetch Contract Backend
Focus:
- Backend side of candidate `3`.
- Contract hardening needed for candidates `1-2`.
- Candidate `6` backend merge work.

Allowed files:
- `src/api/game/spatial.py`
- `src/api/game/prefetch.py`
- `src/models/schemas.py`
- `src/services/spatial_navigator.py`
- `src/services/prefetch_service.py`
- `tests/contract/test_spatial_navigation.py`
- `tests/contract/test_spatial_move.py`
- `tests/contract/test_spatial_map.py`
- `tests/api/test_prefetch_endpoints.py`
- `tests/service/test_spatial_navigator.py`
- `tests/service/test_prefetch_service.py`
- `tests/integration/test_spatial_navigation_integration.py`

### Lane 3: Legacy Ingest/Runtime Pruning
Focus:
- Candidates `4`, `5`, `7`.

Allowed files:
- `src/services/story_smoother.py`
- `src/services/auto_improvement.py`
- `src/services/storylet_ingest.py`
- `src/services/seed_data.py`
- `src/api/game/state.py`
- `src/api/game/__init__.py`
- `src/api/author/__init__.py`
- `src/config.py`
- `tests/service/test_storylet_ingest.py`
- `tests/service/test_decomposed_functions.py`
- `tests/service/test_seed_data.py`
- `tests/api/test_game_endpoints.py`
- `tests/api/test_author_generate_world_confirmation.py`
- `tests/api/test_route_smoke.py`

### Lane 4: Gate/Tooling Demotion
Focus:
- Candidate `8` and command-surface simplification.

Allowed files:
- `scripts/dev.py`
- `pyproject.toml`
- `.github/workflows/*.yml`
- `README.md`
- `client/README.md`
- `improvements/refactor_phase_checklist.md`
- `improvements/HARNESS_BOOTSTRAP_CHECKLIST.md`
- `improvements/ROADMAP.md`

Rule:
- Every lane is forbidden from editing files outside its allowed set.

## Interface Contracts Between Lanes
### Contract C1: Spatial Navigation Payload (Lane 2 owner, Lane 1 consumer)
Shape:
```json
{
  "position": { "x": "int", "y": "int" },
  "directions": ["string"],
  "location_storylet": { "id": "int", "title": "string", "position": { "x": "int", "y": "int" } } | null,
  "leads": [{ "direction": "string", "title": "string", "score": "number", "hint": "string?" }],
  "semantic_goal": "string|null",
  "goal_hint": "string|null"
}
```
Rules:
- No required-field removals.
- Any new fields must be additive and optional.

### Contract C2: Movement API + Blocked-Move Semantics (Lane 2 owner, Lane 1 consumer)
Request:
```json
{ "direction": "string" }
```
Success response:
```json
{ "result": "string", "new_position": { "x": "int", "y": "int" } }
```
Error semantics:
- `403` blocked move remains `detail="Cannot move in that direction"`.
- Lane 1 may change UX handling, but not backend error contract.

### Contract C3: Prefetch API Surface (Lane 2 owner, Lane 1 consumer)
- `POST /api/prefetch/frontier` request: `{ "session_id": "string" }`, response: `{ "triggered": true|false }`.
- `GET /api/prefetch/status/{session_id}` response keys stay exactly:
  - `stubs_cached: int`
  - `expires_in_seconds: int`

### Contract C4: Session Reset Payload (Lane 3 owner, Lane 1 consumer)
Response fields retained:
- `success`
- `message`
- `deleted`
- `storylets_seeded`
- `legacy_seed_mode`

Demotion/isolation of legacy seed behavior must keep payload shape stable.

### Contract C5: Author Ingest Result Envelope (Lane 3 owner, API consumers/tests)
`postprocess_new_storylets()` return keys retained:
- `added`
- `skipped`
- `storylets`
- `spatial_updates`
- `auto_improvements`
- `improvement_details`

### Contract C6: Action Stream Event Payload (Frozen, no lane edits this cycle)
`/api/action/stream` SSE event names and payload semantics remain:
- `draft_chunk` -> `{ "text": "string" }`
- `final` -> `ActionResponse`
- `error` -> `{ "detail": "string" }`

## Integration Order and Lane Validation Commands
1. Lane 2 (backend contracts first)
Required validation:
- `python -m pytest -q tests/contract/test_spatial_navigation.py tests/contract/test_spatial_move.py tests/contract/test_spatial_map.py tests/service/test_spatial_navigator.py tests/api/test_prefetch_endpoints.py tests/service/test_prefetch_service.py tests/integration/test_spatial_navigation_integration.py`

2. Lane 3 (legacy/runtime pruning with payload stability)
Required validation:
- `python -m pytest -q tests/service/test_storylet_ingest.py tests/service/test_decomposed_functions.py tests/service/test_seed_data.py tests/api/test_game_endpoints.py tests/api/test_author_generate_world_confirmation.py tests/api/test_route_smoke.py`

3. Lane 1 (client demotion/isolation after backend contracts settle)
Required validation:
- `npm --prefix client run build`
- `python -m pytest -q tests/contract/test_spatial_navigation.py tests/contract/test_spatial_move.py`

4. Lane 4 (tooling/gate demotion last)
Required validation:
- `python -m ruff check src/api src/services src/models main.py`
- `python -m black --check src/api src/services src/models main.py`
- `python scripts/dev.py verify`

5. Final integration gate (all lanes merged)
Required validation:
- `python -m pytest -q`
- `npm --prefix client run build`

## Execution Notes
- Follow pruning protocol: baseline freeze, bounded commits, validation evidence, rollback notes.
- Prefer delete/merge over adding new abstractions.
- If cross-lane dependency blocks progress, stop and record blocker evidence rather than editing outside boundary.
