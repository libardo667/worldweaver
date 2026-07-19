# Directory Pruning Audit — 2026-03-13

First-pass disposition for every file in the repo.
Verdicts: ✅ confirmed keep | 🗑️ safe to delete | 📦 archive but keep | ❓ ask for details

---

## ROOT LEVEL (complete)

| File | Verdict | Notes |
|------|---------|-------|
| `.cloudflared/config.yml` | ✅ keep | Cloudflare tunnel config |
| `.dockerignore`, `Dockerfile`, `docker-compose.yml` | ✅ keep | |
| `.env`, `.env.example`, `.gitignore` | ✅ keep | |
| `AGENTS.md`, `CLAUDE.md`, `README.md` | ✅ keep | README rewritten 2026-03-13 |
| `alembic.ini`, `pyproject.toml`, `requirements.txt`, `main.py` | ✅ keep | |
~~| `.coverage` | 🗑️ delete | runtime artifact |~~
~~| `test_database.db`, `worldweaver.db` | 🗑️ delete | runtime artifacts |~~
~~| `arc_scan.txt` | ❓ ask | one-off diagnostic dump? |~~
~~| `find_boms.py` | ❓ ask | one-off BOM-hunting script? |~~
~~| `playtest.py` | ❓ ask | vs `playtest_harness/harness.py` — duplicate entry point? |~~
~~| `test_imports.py` | ❓ ask | standalone import check or dead? |~~

---

## ALEMBIC (complete)

| File | Verdict |
|------|---------|
| `alembic/env.py`, `alembic/script.py.mako`, `alembic/README` | ✅ keep |
| All `alembic/versions/*.py` | ✅ keep — schema history |

---

## SRC — Core (unambiguously live) (complete)

| File | Verdict |
|------|---------|
| `src/config.py`, `src/database.py` | ✅ keep |
| `src/models/__init__.py`, `src/models/schemas.py` | ✅ keep |
| `src/core/scene_card.py` | ✅ keep |
| `src/services/world_memory.py` | ✅ keep |
| `src/services/command_interpreter.py` | ✅ keep |
| `src/services/llm_client.py`, `llm_json.py`, `llm_service.py` | ✅ keep |
| `src/services/embedding_service.py` | ✅ keep |
| `src/services/model_registry.py`, `runtime_metrics.py`, `cache.py` | ✅ keep |
| `src/services/session_service.py`, `game_logic.py` | ✅ keep |
| `src/services/city_pack_seeder.py`, `city_pack_service.py` | ✅ keep |
| `src/services/location_mapper.py` | ✅ keep |
| `src/services/rules/reducer.py`, `rules/schema.py` | ✅ keep |
| `src/services/grounding.py` | ✅ keep |
| `src/api/game/turn.py`, `world.py`, `orchestration_adapters.py`, `runtime_helpers.py` | ✅ keep |

---

## SRC — Needs Discussion

| File | Verdict | Question |
|------|---------|----------|
~~| `src/services/spatial_navigator.py` | 🗑️ deleted | Major 09 (2026-03-13) |~~
~~| `src/api/game/spatial.py` | 🗑️ deleted | Major 09 (2026-03-13) |~~
~~| `src/services/world_bootstrap_service.py` | 🗑️ deleted | 2026-03-13 — V3 LLM world generation, never reached in V4 city-pack flow |~~
| `src/api/game/story.py` | ✅ keep | This IS `POST /api/next` — the core turn endpoint, misleadingly named |
~~| `src/services/storylet_analyzer.py` | 🗑️ deleted | Major 11 (2026-03-13) — author-only service |~~
| `src/services/storylet_ingest.py` | ✅ keep (Major 10) | Batch storylet insertion; called from seed_data + state.py |
| `src/services/storylet_selector.py` | ✅ keep (Major 10) | `pick_storylet_enhanced` — called by story.py, action.py, turn_service (×4), orchestration_adapters |
| `src/services/storylet_utils.py` | ✅ keep (Major 10) | `normalize_choice`, `find_storylet_by_location` — called at 6 sites |
| `src/services/semantic_selector.py` | ✅ keep (Major 10) | Semantic scoring / context vectors; called by turn_service (×2) |
| `src/services/prefetch_service.py` | ✅ keep (Major 10) | 1196-line frontier prefetch cache; called by story, action, turn, state, orchestration_adapters |
| `src/api/game/prefetch.py` | ✅ keep (Major 10) | `/prefetch/frontier` + `/prefetch/status` — admin/debug endpoints |
| `src/services/simulation/systems.py` | ✅ keep | Live — `tick_world_simulation` called at 5+ sites in turn_service.py |
| `src/services/simulation/tick.py` | ✅ keep | Same |
~~| `src/services/story_deepener.py` | 🗑️ deleted | Major 17 (2026-03-13) |~~
~~| `src/services/story_smoother.py` | 🗑️ deleted | Major 17 (2026-03-13) |~~
~~| `src/services/auto_improvement.py` | 🗑️ deleted | Major 17 (2026-03-13) |~~
| `src/services/seed_data.py` | ✅ keep | Seeds dev/legacy storylets on startup; called from state.py |
| `src/services/prompt_library.py` | ✅ keep | 849-line prompt store; called from llm_service (entry cards + more) |
| `src/services/requirements.py` | ✅ keep | `evaluate_requirements()` — storylet gating logic used by game_logic + state_manager |
| `src/services/db_json.py` | ✅ keep | 34-line JSON tolerance helpers; used by session_service + storylet_utils |
~~| `src/services/constellation_service.py` | 🗑️ deleted | 2026-03-13 — constellation cluster removed |~~
~~| `src/api/semantic.py` | 🗑️ deleted | 2026-03-13 — constellation cluster removed |~~
| `src/api/auth/routes.py` | ✅ keep | `/auth/register`, `/auth/login`, `/auth/me` — all called by EntryScreen.tsx; `email_validator` test errors are a missing dev dep, not dead code |
~~| `src/api/author/generate.py` | 🗑️ deleted | Major 11 (2026-03-13) — entire author package removed |~~
~~| `src/api/author/populate.py` | 🗑️ deleted | Major 11 (2026-03-13) |~~
~~| `src/api/author/suggest.py` | 🗑️ deleted | Major 11 (2026-03-13) |~~
~~| `src/api/author/world.py` | 🗑️ deleted | Major 11 (2026-03-13) |~~
| `src/api/game/action.py` | ✅ keep | `POST /api/action` + `/action/stream` — both called by client (`postAction`, `streamAction`) |
| `src/api/game/entities.py` | ✅ keep | `POST /entities/spawn-batch` — CSV-driven resident workspace generator (admin tool) |
| `src/api/game/metrics.py` | ✅ keep | 16-line dev-only `GET /debug/metrics`, gated by `enable_dev_reset` |
| `src/api/game/settings_api.py` | ✅ keep | `/settings/readiness`, `/models`, `/model` — all called by client |
| `src/services/state_manager.py` | ✅ keep | `AdvancedStateManager` — imported by 6 live files (scene_card, reducer, session_service, simulation, storylet_selector) |
| `src/services/state/_types.py` | ✅ keep | M105 domain types; imported by state_manager.py |
| `src/services/state/_utils.py` | ✅ keep | Same |
| `src/services/state/beats.py` | ✅ keep | `NarrativeBeatsDomain` — imported by state_manager.py |
| `src/services/state/goals.py` | ✅ keep | `GoalDomain`, `GoalState` — imported by state_manager.py |
| `src/services/state/inventory.py` | ✅ keep | `InventoryDomain`, `ItemState` — imported by state_manager.py |
| `src/services/state/relationships.py` | ✅ keep | `RelationshipDomain`, `RelationshipState` — imported by state_manager.py |
| `src/services/email_service.py` | ✅ keep | Welcome email via Resend; called from auth/routes.py on signup |

---

## TESTS — Core (keep) (complete)

| File | Verdict |
|------|---------|
| `tests/conftest.py`, `tests/helpers/` | ✅ keep |
| `tests/api/test_game_endpoints.py`, `test_action_endpoint.py`, `test_turn_endpoint.py`, `test_world_endpoints.py`, `test_route_smoke.py`, `test_minimal.py` | ✅ keep |
| `tests/service/test_reducer.py`, `test_world_memory.py`, `test_command_interpreter.py`, `test_embedding_service.py`, `test_session_service.py` | ✅ keep |
| `tests/integration/test_turn_progression_simulation.py` | ✅ keep — canonical soak gate |
| `tests/integration/test_session_persistence.py`, `test_concurrent_session_requests.py` | ✅ keep |

---

## TESTS — Needs Discussion

| File | Verdict | Question |
|------|---------|----------|
| `tests/service/state/` (4 files) | ✅ keep | Tests for live state domain components (M105); all confirmed live |
| `tests/service/test_projection_bfs.py` | ❓ ask | BFS projection is a pruning target |
| `tests/service/test_world_projection.py` | ❓ ask | Same |
~~| `tests/contract/test_spatial_assign.py` | 🗑️ deleted | Major 09 (2026-03-13) |~~
~~| `tests/contract/test_spatial_map.py` | 🗑️ deleted | Major 09 (2026-03-13) |~~
~~| `tests/contract/test_spatial_move.py` | 🗑️ deleted | Major 09 (2026-03-13) |~~
~~| `tests/contract/test_spatial_navigation.py` | 🗑️ deleted | Major 09 (2026-03-13) |~~
~~| `tests/integration/test_spatial_navigation_integration.py` | 🗑️ deleted | Major 16 (2026-03-13) |~~
~~| `tests/integration/test_parameter_sweep_harness.py` | 🗑️ deleted | Major 16 (2026-03-13) |~~
~~| `tests/integration/test_parameter_sweep_metrics.py` | 🗑️ deleted | Major 16 (2026-03-13) |~~
~~| `tests/integration/test_parameter_sweep_phase_a.py` | 🗑️ deleted | Major 16 (2026-03-13) |~~
~~| `tests/integration/test_parameter_sweep_prefetch_reset.py` | 🗑️ deleted | Major 16 (2026-03-13) |~~
~~| `tests/integration/test_parameter_sweep_ranking.py` | 🗑️ deleted | Major 16 (2026-03-13) |~~
~~| `tests/integration/test_narrative_eval_harness.py` | 🗑️ deleted | Major 16 (2026-03-13) |~~
~~| `tests/integration/test_benchmark_three_layer.py` | 🗑️ deleted | Major 16 (2026-03-13) |~~
~~| `tests/diagnostic/test_spatial_map_visual.py` | 🗑️ deleted | Major 09 (2026-03-13) — entire diagnostic/ dir gone |~~
~~| `tests/integration/narrative_eval_baseline.json` | 🗑️ deleted | Major 16 (2026-03-13) |~~
~~| `tests/integration/narrative_eval_scenarios.json` | 🗑️ deleted | Major 16 (2026-03-13) |~~
| `tests/fixtures/state/v1_flat_snapshot.json` | ❓ ask | Migration fixtures for V1/V2 state |
| `tests/fixtures/state/v2_full_snapshot.json` | ❓ ask | Same |
| `tests/fixtures/state/v2_partial_snapshot.json` | ❓ ask | Same |
~~| `tests/integration_harness_helpers.py` | 🗑️ deleted | Major 16 (2026-03-13) — orphaned after sweep test deletion |~~
| `tests/integration_helpers.py` | ✅ keep | Live — used by turn progression + concurrency tests |
| `tests/integration_state_helpers.py` | ✅ keep | Live — used by session persistence tests |
~~| `tests/api/test_author_generate_world_confirmation.py` | 🗑️ deleted | Major 11 (2026-03-13) |~~
~~| `tests/api/test_author_generation.py` | 🗑️ deleted | Major 11 (2026-03-13) |~~
~~| `tests/api/test_author_validation.py` | 🗑️ deleted | Major 11 (2026-03-13) |~~
~~| `tests/api/test_semantic_constellation_endpoint.py` | 🗑️ deleted | 2026-03-13 — constellation cluster removed |~~
~~| `tests/service/test_storylet_analyzer.py` | 🗑️ deleted | Major 11 (2026-03-13) |~~
| `tests/service/test_storylet_ingest.py` | ❓ ask | Same |
| `tests/service/test_storylet_selector.py` | ❓ ask | Same |
| `tests/service/test_storylet_utils.py` | ❓ ask | Same |
~~| `tests/service/test_auto_improvement.py` | 🗑️ deleted | Major 17 (2026-03-13) |~~
| `tests/service/test_decomposed_functions.py` | ❓ ask | What functions? |

---

## SCRIPTS

| File | Verdict | Notes |
|------|---------|-------|
| `scripts/dev.py` | ✅ keep | |
| `scripts/seed_world.py` | ✅ keep | Moved here from ww_agent 2026-03-13 |
| `scripts/canon_reset.py` | ✅ keep | |
| `scripts/build_city_pack.py` | ✅ keep | |
| `scripts/city_configs/portland.json` | ✅ keep | |
| `scripts/city_configs/san_francisco.json` | ✅ keep | |
| `scripts/repair_graph.py` | ✅ keep | maintenance tool |
| `scripts/reembed.py` | ✅ keep | maintenance tool |
~~| `scripts/build_city_pack.py.bak` | 🗑️ delete | leftover backup |~~
| `scripts/benchmark_three_layer.py` | ✅ keep | Invoked by `dev.py benchmark`; live harness tool |
| `scripts/eval_narrative.py` | ✅ keep | Invoked by `dev.py eval` + `dev.py eval-smoke`; live regression harness |
| ~~`scripts/extract_sf_config.py`~~ | 🗑️ deleted | Already gone from filesystem |
| ~~`scripts/merge_playtest.py`~~ | 🗑️ deleted | Already gone from filesystem |
| ~~`scripts/merge_simple_playtest.py`~~ | 🗑️ deleted | Already gone from filesystem |
| ~~`scripts/prune_slow_models.py`~~ | 🗑️ deleted | Already gone from filesystem |
| `scripts/rebuild_projection.py` | ✅ keep | Maintenance CLI for WorldProjection rebuild; calls `rebuild_world_projection()` in world_memory.py; keep until Major 15 |
~~| `scripts/check-task-prerequisites.sh` | 🗑️ deleted | 2026-03-13 — harness-era, not referenced anywhere |~~
~~| `scripts/create-new-feature.sh` | 🗑️ deleted | Same |~~
~~| `scripts/get-feature-paths.sh` | 🗑️ deleted | Same |~~
~~| `scripts/setup-plan.sh` | 🗑️ deleted | Same |~~
~~| `scripts/common.sh` | 🗑️ deleted | Same |~~
~~| `scripts/update-agent-context.sh` | 🗑️ deleted | Same |~~

---

## IMPROVEMENTS

| File/Group | Verdict | Notes |
|------------|---------|-------|
| `prune/VISION.md` | ✅ keep | |
| `prune/ROADMAP.md` | ✅ keep | |
| `prune/pytest-warning-baseline.json` | ✅ keep | CI gate |
| `prune/majors/06-agent-life-visibility.md` | ✅ keep | active backlog |
| `prune/majors/07-inter-city-travel.md` | ✅ keep | active backlog |
| `prune/majors/08-onboarding-surface.md` | ✅ keep | active backlog |
~~| `prune/minors/minor_118.md` | ✅ keep | active backlog |~~ --> was already completed; archived.
| `prune/minors/MINOR_SCHEMA.md` | ✅ keep | |
| `prune/majors/MAJOR_SCHEMA.md` | ✅ keep | |
| `prune/harness/*.md` (11 docs + README) | ❓ ask | Is the full harness workflow still the V4 process, or V3-era overhead? | --> let's talk about this more directly. I am considering marketing this harness apporach for working with LLM coding agents and want to refine it based on how it has worked in this project.
| `prune/harness/templates/` (9 templates) | ❓ ask | Same |
~~| `prune/MULTI_TEMPO_AGENTS.md` | ❓ ask | Design doc; superseded by ww_agent or still reference? | ~~ --> ww_agent now has this plan implemented. deleted.
| `prune/GROUNDING_PLAN.md` | ❓ ask | Still live? | --> yes and if it is not in the vision/roadmap .md files, it should be folded in.
| `prune/SPATIAL_NAVIGATION.md` | ❓ ask | SpatialNavigator is a pruning target | --> see above comments about SpatialNavigator
~~| `prune/WORLD_RESET.md` | ❓ ask | Superseded by canon_reset.py docs? |~~
~~| `prune/refactor_phase_checklist.md` | ❓ ask | V3 refactor; done or ongoing? |~~
~~| `prune/lint-baseline.md` | 📦 archive | historical |~~
~~| `prune/HARNESS_BOOTSTRAP_CHECKLIST.md` | 📦 archive | historical process doc |~~
~~| `prune/majors/archive/` (~60 files) | 📦 archive | completed work history |~~
~~| `prune/minors/archive/` (~100 files) | 📦 archive | completed work history |~~
~~| `prune/history/` (~35 files) | 📦 archive | audit trail / PR evidence |~~
~~| `prune/history/pruning_run_2026-03-06/` (~50 files + evidence/) | 🗑️ deleted | Major 12 (2026-03-13) — consolidated to `prune/history/pruning_run_2026-03-06_summary.md` |~~
~~| `prune/prompts/old_improvement_prompt.md` | ❓ ask | How old? Still used? |~~
~~| `prune/prompts/pruning_prompts.md` | ❓ ask | Agent prompts? still used? |~~
~~| `prune/prompts/startup_prompts.md` | ❓ ask | Same |~~
~~| `prune/pruning/build_reachability_evidence.py` | 📦 archive | |~~
~~| `prune/pruning/execute_batch_a_relocation.ps1` | 📦 archive | |~~

---

## CLIENT

| File | Verdict | Notes |
|------|---------|-------|
| `client/src/App.tsx`, `main.tsx`, `styles.css`, `types.ts` | ✅ keep | |
| `client/src/api/wwClient.ts` | ✅ keep | |
| `client/src/components/*.tsx` (all 6) | ✅ keep | |
| `client/src/state/sessionStore.ts` | ✅ keep | |
| `client/index.html`, `vite.config.ts`, `package.json`, `tsconfig.json` | ✅ keep | |
~~| `client/tsconfig.tsbuildinfo` | 🗑️ delete | build artifact |~~
~~| `client/tsconfig.node.tsbuildinfo` | 🗑️ delete | build artifact |~~
~~| `client/src/views/ConstellationView.tsx` | 🗑️ deleted | 2026-03-13 — never imported in App.tsx; backend gone |~~
~~| `client/README.md` | ❓ ask | Default Vite boilerplate or real content? | --> not boilerplate but it is old, and i think superseded by the root's README.md. Please compare, collapse into root README and delete client.~~
~~| `client/.env.local` | ❓ ask | What's in it? should it be gitignored? |~~ --> all that was in here was "VITE_WW_ENABLE_CONSTELLATION=1". Since we are cutting out constellation view, I deleted.

--> not sure why @client/ has its own .gitignore

---

## DATA (complete)

| File/Group | Verdict | Notes |
|------------|---------|-------|
| `data/world_id.txt` | ✅ keep | |
| `data/cities/` | ✅ keep | SF + Portland city packs |
~~| `data/player_inboxes/` | ❓ ask | 354 files across 12 session folders — runtime data; should this be gitignored? Are these sessions worth keeping? |~~ --> these should be deleted on canon_reset.py activation. i deleted the contents of player_inboxes as of now.

---

## PLAYTEST HARNESS --> not how i'm testing anymore, but it could be useful for someone. will archive and not delete.

~~| File | Verdict | Notes |~~
~~|------|---------|-------|~~
~~| `playtest_harness/LLM_PLAYTEST_GUIDE.md` | 📦 archive | |~~
~~| `playtest_harness/harness.py` | ❓ ask | V3 harness tooling; still maintained for V4? |~~
~~| `playtest_harness/llm_playtest.py` | ❓ ask | Same |~~
~~| `playtest_harness/long_run_harness.py` | ❓ ask | Same |~~
~~| `playtest_harness/parameter_sweep.py` | ❓ ask | Same |~~
~~| `playtest_harness/input.txt` | ❓ ask | Test inputs for V3 world; stale? |~~
~~| `playtest_harness/input_fantasy.txt` | ❓ ask | Same |~~

---

## Summary

| Category | Approx count |
|----------|-------------|
| ✅ Confirmed keep | ~85 files |
| 🗑️ Deleted (2026-03-13 session) | ~35 files |
| 🗑️ Safe to delete now | ~8 files |
| 📦 Archive but keep | ~180 files |
| ❓ Needs discussion | ~45 files |

### Completed in 2026-03-13 session

- **Major 09** (spatial navigator): `spatial_navigator.py`, `spatial.py`, 4 spatial contract tests, `tests/diagnostic/` dir — all deleted. Turn service `get_spatial_navigator_fn` parameter threading removed (tail commit a49d623). Archived.
- **Major 11** (author pipeline): entire `src/api/author/` package, `storylet_analyzer.py`, 4 author/analyzer tests — all deleted. Archived.
- **Major 12** (pruning history): `prune/history/pruning_run_2026-03-06/` (~50 files) consolidated to single summary. Archived.
- **Major 16** (V3 sweep/eval tests): 7 parameter sweep tests, 2 eval harness tests, `integration_harness_helpers.py`, 2 JSON fixtures — all deleted. Archived.
- **Major 17** (story_smoother/deepener/auto_improvement): All 3 service files + test deleted; call sites removed from game_logic, storylet_ingest, world_bootstrap_service; config flags removed; `build_bridge_prompt` removed from prompt_library. Archived.
- **world_bootstrap_service + session/start** (2026-03-13): `world_bootstrap_service.py` deleted; `POST /session/start` endpoint removed; dead unreachable code block in `/session/bootstrap` removed; non-city-pack else branch in `/api/world/seed` removed; `SessionStartResponse` schema deleted; 8 dead tests removed. -675 lines.
- **Constellation cluster**: `constellation_service.py`, `src/api/semantic.py`, `test_semantic_constellation_endpoint.py`, 4 schema models, semantic router from main.py, `enable_constellation` from config — all deleted.
- **.env cleanup**: Removed 20 redundant/dead lines; dead `NAVIGATOR_CACHE_*` settings, disabled `WW_ENABLE_V3_PLAYER_HINT_CHANNEL`, all flags that matched defaults.

### Remaining open question clusters

1. **Storylet pipeline** (Major 10, long-term) — all 6 files confirmed live and deeply wired into the V4 turn pipeline. `prefetch_service.py` alone is 1196 lines. Replacing this cluster requires a design decision about the turn selection mechanism, not just cleanup.
2. **BFS projection** — `test_projection_bfs.py`, `test_world_projection.py`, `scripts/rebuild_projection.py`. Tied to WorldProjection table (Major 15).
3. **V3 eval scripts** — `scripts/benchmark_three_layer.py`, `scripts/eval_narrative.py` — both confirmed referenced by dev.py (`benchmark`, `eval`, `eval-smoke` commands). ✅ keep.
4. **Missing dev dep** — `email-validator` (`pydantic[email]`) not installed locally; causes ~170 test collection errors in auth-adjacent tests. Run `pip install pydantic[email]` to fix.

### Safe deletes (no discussion needed)

```
.coverage
test_database.db
worldweaver.db
scripts/build_city_pack.py.bak
client/tsconfig.tsbuildinfo
client/tsconfig.node.tsbuildinfo
arc_scan.txt          # if confirmed one-off
find_boms.py          # if confirmed one-off
```

---
---

# ww_agent Pruning Audit — 2026-03-13

First-pass disposition for every file in `ww_agent/`.
Verdicts: ✅ confirmed keep | 🗑️ safe to delete | 📦 archive but keep | ❓ ask for details

---

## ROOT LEVEL

| File | Verdict | Notes |
|------|---------|-------|
| `README.md` | ✅ keep | |
| `AGENTS.md` | ✅ keep | Substantially updated 2026-03-13 with fast+wander docs |
| `LICENSE` | ✅ keep | |
| `Dockerfile` | ✅ keep | |
| `.env` | ✅ keep | |
| `.gitignore` | ✅ keep | |
| `pyproject.toml` | ✅ keep | |
| `.ruff_cache/` | 🗑️ delete | tool cache, should be gitignored |

---

## CONFIG

| File | Verdict | Notes |
|------|---------|-------|
| `config/README.md` | ✅ keep | |
| `config/env.example` | ✅ keep | |

---

## SRC — Core loops (all confirmed live)

| File | Verdict | Notes |
|------|---------|-------|
| `src/__init__.py`, `src/main.py` | ✅ keep | Entry point + loop orchestration |
| `src/resident.py` | ✅ keep | Agent state container |
| `src/loops/__init__.py`, `src/loops/base.py` | ✅ keep | |
| `src/loops/fast.py` | ✅ keep | Classifier + dispatcher (8 slugs) |
| `src/loops/slow.py` | ✅ keep | |
| `src/loops/wander.py` | ✅ keep | Route keeper (no-LLM BFS hop advancement) |
| `src/loops/doula.py` | ✅ keep | |
| `src/loops/mail.py` | ✅ keep | |
| `src/loops/ground.py` | ✅ keep | Grounding handler |
| `src/loops/README.md` | ✅ keep | |

---

## SRC — Identity

| File | Verdict | Notes |
|------|---------|-------|
| `src/identity/__init__.py`, `src/identity/loader.py` | ✅ keep | |
| `src/identity/README.md` | ✅ keep | |

---

## SRC — Memory

| File | Verdict | Notes |
|------|---------|-------|
| `src/memory/__init__.py` | ✅ keep | |
| `src/memory/working.py` | ✅ keep | |
| `src/memory/retrieval.py` | ✅ keep | |
| `src/memory/provisional.py` | ✅ keep | |
| `src/memory/README.md` | ✅ keep | |

---

## SRC — World Client

| File | Verdict | Notes |
|------|---------|-------|
| `src/world/__init__.py`, `src/world/client.py` | ✅ keep | HTTP client to worldweaver backend |
| `src/world/README.md` | ✅ keep | |

---

## SRC — Inference

| File | Verdict | Notes |
|------|---------|-------|
| `src/inference/__init__.py`, `src/inference/client.py` | ✅ keep | LLM wrapper |
| `src/inference/README.md` | ✅ keep | |

---

## TESTS

| File | Verdict | Notes |
|------|---------|-------|
| `tests/__init__.py` | ✅ keep | |
| `tests/README.md` | ✅ keep | |

> **Note:** ww_agent has no actual test files beyond `__init__.py` and the README. This is a gap worth noting for future work.

---

## SCRIPTS

| File | Verdict | Notes |
|------|---------|-------|
| `scripts/README.md` | ✅ keep | |
| ~~`scripts/seed_world.py`~~ | 🗑️ deleted | Moved to `worldweaver/scripts/` 2026-03-13 |

> scripts/ is now empty of Python files. The README may need updating.

---

## RESIDENTS — Identity & Config (all confirmed keep)

Each resident follows the same structure. All nine are active:
`darnell`, `elias`, `fei_fei`, `ingrid`, `kwame`, `ray`, `rosario`, `sun_li`, `zhang`

| File pattern | Verdict | Notes |
|-------------|---------|-------|
| `residents/<name>/identity/IDENTITY.md` | ✅ keep | Agent backstory/personality |
| `residents/<name>/identity/SOUL.md` | ✅ keep | Deep character doc |
| `residents/<name>/identity/soul_notes.md` | ✅ keep | Iteration notes |
| `residents/<name>/identity/tuning.json` | ✅ keep | Loop timing + model config |
| `residents/_template/` | ✅ keep | Scaffold for new residents |
| `residents/_contracts/levi.json` | ✅ keep | Player protection contract (added 2026-03-13) |

---

## RESIDENTS — Runtime State (gitignore candidates)

These are live runtime files that accumulate during agent operation. They are currently tracked in git, which creates noisy diffs and may expose internal agent state. Recommend adding patterns to `.gitignore`.

| File pattern | Verdict | Notes |
|-------------|---------|-------|
| `residents/<name>/decisions/decision_*.json` | ❓ ask | Fast loop decision logs; useful for debugging but noisy in git. Gitignore or keep? |
| `residents/<name>/memory/working.json` | ❓ ask | Ephemeral working memory; resets each loop. Should be gitignored |
| `residents/<name>/memory/long_term.json/*.json` | ❓ ask | Timestamped long-term memories; valuable personal history. Keep in git or gitignore + backup separately? |
| `residents/<name>/session_id.txt` | ❓ ask | Last session ID; runtime artifact. Gitignore? |
| `residents/sun_li/letters/intents/intent_*.md` | ❓ ask | Letter intent files; runtime. Gitignore? |
| `residents/.doula_polls.json` | ❓ ask | Doula consensus state; runtime artifact. Gitignore? |
| `residents/.doula_spawns.json` | ❓ ask | Doula spawn tracking; runtime artifact. Gitignore? |

**Proposed `.gitignore` additions for ww_agent:**
```
residents/*/decisions/decision_*.json
residents/*/memory/working.json
residents/*/session_id.txt
residents/*/letters/intents/intent_*.md
residents/.doula_polls.json
residents/.doula_spawns.json
# long_term memories — discuss before ignoring
```

---

## ww_agent Summary

| Category | Count |
|----------|-------|
| ✅ Confirmed keep | ~45 files |
| 🗑️ Safe to delete / gitignore | ~5 files + ruff cache |
| ❓ Needs discussion | ~90 runtime state files |

### Biggest open questions

1. **Runtime state in git** — decisions, working memory, session IDs, letter intents, doula state are all accumulating as committed files. Should they be gitignored (clean repo) or kept (debugging aid)?
2. **Long-term memories** — these are the most valuable runtime files. If gitignored, need a backup/export mechanism before they're lost on `git clean`.
3. **Tests gap** — no actual test files exist. Fast loop, wander loop, identity loading, memory retrieval — all untested. Worth a minor ticket?
4. **scripts/README.md** — now points to `seed_world.py` which was moved. Needs a one-line update.
