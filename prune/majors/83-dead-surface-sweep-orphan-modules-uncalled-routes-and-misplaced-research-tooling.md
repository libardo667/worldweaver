# Sweep the verified-dead surface: orphan modules, uncalled API routes, and misplaced research tooling

## Ownership correction (2026-07-14)

The former `sync_substrate.py` tool, manifest, baseline, and dedicated tests were retired with archived
Major 76. WorldWeaver now owns the substrate; Stable is source history, not an operational upstream. The
older slice notes below remain execution history, not a current instruction to preserve sync machinery.

## Update (2026-07-18) — test-inclusive graph follow-up

A fresh full graph at commit `85f55f5`, this time including tests, reduced fifteen raw island candidates to
three after lazy-import and entry-point verification. All three were deleted rather than wired:

- `services/db_json.py` was a generic JSON helper imported only by its own test;
- `services/model_registry.py` estimated fictional ten-turn narrator sessions from a stale hand-written
  price table. Current spend work belongs to resident pulse receipts and provider reconciliation under
  Major 70, not an engine-side model picker; and
- `services/simulation/` was still imported only by its own test. Its single system automatically raised
  danger on each turn to manufacture narrative pressure, contradicting the neutral-world rule. It also
  referenced the already-deleted delta `delete` field and swallowed the resulting error after partially
  mutating its aggregate.

The old `simulation_tick` world-event label remains recognized so historical records do not change meaning.
The unused producer, config flag, reducer intent, package, and self-contained tests are gone. A separate
audit is required before changing the wider event reducer: production services use the canonical event
submission boundary, but initial inspection suggests its typed intent classes may now be test-only.

The generated tour's “rules → narration” description is not current architecture. Engine model calls now
serve embeddings and optional pre-habitation city-pack drafting; human and resident actions do not enter an
engine narrator.

## Update (2026-07-12) — slice 1 executed; one finding corrected

Execution began on branch `major-83-slice-1-dead-surface`, leaf-first per plan.

- **Slice 1a shipped (46cf99b):** deleted `ww_agent/src/memory/` (whole package),
  `runtime/rest.py`, `runtime/retrieval.py`, and their dedicated tests. `test_reducers.py` now
  appends `research_queued` ledger events directly (the removed `ResearchQueue` was a loop-era
  *writer wrapper* around the ledger — the live queue was already a reducer). Agent suite: 241
  passed; the 1 failure is pre-existing and unrelated (`test_sync_substrate`: the-stable's
  `src/runtime/source_gate.py` is unmanifested — **belongs to Major 76**, flagged there).
- **Slice 1b shipped (c091c64):** deleted `api/game/turn.py` + router registration +
  `enable_turn_endpoint` flag + `TurnRequest`/`TurnResponse` schemas + its tests. Engine suite:
  739 passed; app boots with 87 routes; `/api/next` intact.
- **Finding corrected — `/world/rest-metrics` is LIVE, not dead.** The original audit's route
  extraction missed a template-literal fetch: `wwClient.getRestMetrics()` feeds the
  `PresencePanel` in `WorldInfoPane` (and `AppTopbar` gates on it). The engine route **stays**.
  Only the agent-side `rest.py` (the resident rest scheduler) was dead; note the presence panel
  may now show no "resting" sessions since nothing puts residents into rest — if the panel is
  wanted long-term, resting-state emission needs a substrate-side home (keeper call, out of
  slice-1 scope). The "dead pair" language in section A below is superseded by this note.
- Local note: the gitignored scratch script `ww_agent/scripts/_baseline_retrieval.py` imported
  the deleted `runtime/retrieval.py` and is now broken (untracked; delete or archive at will).

## Update (2026-07-12) — slice 2 executed; a second finding corrected

Keeper triaged the orphan-route list (delete all state mutators; delete all world-inspection
routes; keep + document the ops trio; keep + document `/terms`). Executed:

- **Deleted 14 routes** (engine now serves 73, down from 87): the 5 fine-grained state mutators
  (`/state/{}/item|relationship|environment|goal|goal/milestone`), 6 world-inspection routes
  (`/world/event-ledger`, `/world/projection`, `/world/graph/location/{}`,
  `/world/graph/neighborhood`, `/world/{}/events`, `/world/{}/locations/graph`),
  `/entities/spawn-batch` (the whole 334-line `entities.py` module existed to serve it),
  `/dev/jit-test` (called `generate_world_bible` — 69's corpse), and `/prefetch/status/{}`
  (plus its dead client chain: `getPrefetchStatus`, the status localStorage cache fns, and the
  `PrefetchStatusResponse` type). Six orphaned schema classes went with them; `MapMoveRequest`
  was preserved (it lived inside a deleted range but serves the live `/game/move`).
- **Finding corrected — `POST /world/seed` is LIVE, not dead.** `scripts/seed_world.py` calls
  it via an f-string URL (`f"{server}/api/world/seed"`), and it is step 3 of `new_shard.py`
  shard provisioning. The original audit's script-caller extraction only matched quoted literal
  paths — the same failure class as the rest-metrics miss (template/f-string URLs). Kept and
  documented. The full kill list was re-swept for f-string callers after this; the other 14
  were clean.
- **Kept + documented** in `worldweaver_engine/README.md` ("Operational endpoints"):
  `/world/seed`, `/cleanup-sessions`, `/session/prune-duplicate-agents`, `/debug/metrics`,
  `/auth/terms`.
- **Tests:** 15 pure route tests deleted with their routes; 8 live-behavior tests rewritten to
  probe via the service/DB layer instead of deleted inspection routes (goal/environment setup
  through the state manager; prefetch-purge asserts via `get_frontier_status`; projection
  fanout asserts via `WorldProjection` queries).
- **Validation:** ruff clean, black applied, engine suite 720 passed, client `tsc` clean and
  `vite build` green, app boots with 73 routes and zero kill-list survivors.

## Update (2026-07-12) — slices 3+4 executed (f113476)

- **Slice 3:** 17 probes + `fixtures/` + `pen_swap/` moved from `ww_agent/scripts/` to
  `research/probes/` (with a README naming each and the run contract); their two dedicated
  tests moved to `research/probes/tests/` (6 passed there). Shims rewritten; the
  peer-register fixture path verified from the new home. `ww_agent/scripts/` keeps only
  operational tooling (sync_substrate + manifest/baseline, live_boot, pulse_familiars,
  familiar.py, backfill) and its README now describes reality instead of loop-era "planned
  scripts" that were never built.
- **Slice 4:** `src/loops/` is gone. `doula.py` → `src/runtime/doula.py` — **kept the doula
  name** (established vocabulary: `DoulaLoop`, the doula-polls API) instead of the
  "e.g. spawning.py" suggestion above; six import sites updated. The loops `__init__` and the
  SUPERSEDED loops README were deleted (git history is the archive — this supersedes 81's
  earlier "keep as history" note for that file, since the package it documented no longer
  exists). `AGENTS.md` got a minimal SUPERSEDED banner + dead-link strikethroughs only; its
  rewrite remains 81's.
- Validation: agent suite 235 passed (+1 pre-existing Major-76 manifest failure), probe tests
  6 passed, doula imports clean from `src.runtime`, moved probes parse and run through their
  new shims. 25 ruff findings in ww_agent/research are pre-existing (identical on branch base).

Remaining: slice 5 (alembic squash) — **blocked on Majors 68/69** landing their table drops.

## Decision and lineage

A full-repo knowledge-graph pass (2026-07-12; 298 source files, import-graph fan-in analysis, then
**grep verification of every "dead" candidate against live source** — lazy imports fool import graphs)
found a layer of code that is not superseded-but-referenced, but **verified-orphaned**: nothing in the
tracked tree imports it or calls it. Left in place it does what dead code always does here — re-suggests
retired architecture to every fresh agent, pads the two monster route files, and makes the runtime
package unreadable next to 5,500 lines of research probes.

- **Status:** proposed (2026-07-12, recon complete; evidence local at `.ua/knowledge-graph.json`,
  untracked — method documented below so it's reproducible).
- **Owns only the unclaimed remainder.** Overlapping findings are contributed as evidence to their
  existing owners, not re-scoped here:
  - **→ Major 68 (guild):** all 10 engine-side guild routes (`/guild/*` ×7, `/state/{}/guild-*` ×3)
    now have **zero callers anywhere** post-slice-2 (commit b42eab3), plus `/state/{}/adaptation` and
    `/state/{}/social-feedback`. `guild_service.py` (608 lines), `growth_service.py` (340),
    `starter_quests.py` are live only via routes into the void. Confirms 68's slices 3–5 are pure
    demolition with no consumer to sequence around.
  - **→ Major 69 (storylet/turn):** `src/services/storylet_ingest.py` (265 lines) is imported **only by
    its own tests**. `POST /turn` (`api/game/turn.py`, the file's only route) has zero callers — the
    live path is `POST /next` (`story.py`); a standing parallel-path violation.
  - **→ Major 76 (reconvergence):** `src/familiar/` (3 modules) is imported only by
    `scripts/familiar.py`; leaves with the reconvergence.
  - **→ Major 81 (doc drift):** `ww_agent/src/memory/README.md` and `src/loops/README.md` describe the
    packages this major deletes/dissolves; coordinate so 81 doesn't rewrite prose for directories that
    are about to stop existing.

## Problem

**Method.** Route inventory: 96 distinct backend paths extracted from `@router.*` decorators, then
credited against every real consumer — the React client (`wwClient.ts`, incl. the SSE
`/api/action/stream` fetch), the agent (`ww_agent/src/world/*.py`, 29 paths incl. dotted f-strings),
peer shards (federation client calls in `federation_pulse.py` / `federation_identity.py`), and the
eval/maintenance scripts. Module liveness: import-graph fan-in, then `grep` for lazy/function-body
imports before calling anything dead.

### A. Verified-dead modules (~1,500 lines)

- **`ww_agent/src/memory/`** — the entire loop-era three-layer memory package
  (`working|provisional|retrieval|reveries|voice|research_queue.py`, ~500 lines + README). **Zero
  importers.** The live memory is `src/runtime/memory.py`; every `import memories` in the tree
  resolves there.
- **`ww_agent/src/runtime/rest.py`** (462 lines) — zero importers. Also the only code in `ww_agent`
  that reaches across into `worldweaver_engine/` paths (reads a weather-config file). Its engine twin
  `GET /world/rest-metrics` also has zero callers — a dead pair.
- **`ww_agent/src/runtime/retrieval.py`** — sole importer is `scripts/_baseline_retrieval.py`, which
  is **gitignored** (`ww_agent/scripts/_*.py`). Dead in tracked code.
- **`worldweaver_engine/src/api/game/turn.py`** — `POST /turn`, zero callers (evidence owned by 69;
  listed here because the file can be deleted independently of the turn-service demolition).

### B. Orphaned route surface (~20 routes beyond 68/69's scope)

Of 96 paths, ~50 have no client/agent caller; after crediting federation peer traffic and script
callers, and setting aside the guild/adaptation block (→68), these remain **uncalled and unmentioned
in any doc, shard script, or compose file**:

- Fine-grained state mutation: `/state/{}/item`, `/state/{}/relationship`, `/state/{}/goal`,
  `/state/{}/goal/milestone`, `/state/{}/environment` — state changes flow through turn resolution.
- World inspection/admin: `/world/seed`, `/world/projection`, `/world/event-ledger`,
  `/world/map/query`, `/world/map/{}`, `/world/graph/location/{}`, `/world/graph/neighborhood`,
  `/world/{}/events`, `/world/{}/locations/graph`, `/world/dm/my-threads/{}` (×2),
  `/world/rest-metrics`, `/world/digest` (one doc mention).
- Ops/debug: `/entities/spawn-batch`, `/cleanup-sessions`, `/session/prune-duplicate-agents`,
  `/debug/metrics`, `/dev/jit-test`, `/terms`, `/prefetch/status/{}`.

Some of these may be deliberate keeper-curl tools. That is a **triage decision, not a finding** — but
"zero doc references" means each is at minimum undocumented. Most live in the two monster files:
`api/game/world.py` (3,366 lines / 37 routes) and `api/game/state.py` (1,904 / 35).

### C. Misplaced tooling (~7,400 lines in the wrong home)

- **`ww_agent/scripts/` = 31 files / 5,512 lines**, dominated by research instrumentation (pen-swap
  record/replay harness, register/embedding probes, reciprocity, cost curves, three-axis). Nothing in
  the runtime imports any of it. It outweighs the engine's entire API layer and is the main reason the
  Agent Runtime reads as sprawling (82 graph nodes; ~50 after relocation). `research/` exists for
  exactly this.
- **`ww_agent/src/loops/doula.py`** (1,895 lines) — the only survivor in `loops/`. It is the spawn
  orchestrator, not a loop; the vestigial package name keeps the superseded four-loop story looking
  half-alive (the thing 81 exists to stop).

### D. For the record — looked dead, is not

So future auditors don't re-litigate: `federation_pulse`, `city_pack_seeder`, `semantic_selector`,
`action_validation_policy`, `core/scene_card`, and `api/federation/routes` all show zero import-graph
fan-in but are **alive** via lazy/function-body imports or peer-shard HTTP. `seed_data.py` has 4 real
importers including `main.py`. Cross-component hygiene is otherwise excellent: engine and agent touch
only over HTTP.

## Proposed Solution

Leaf-first slices, each independently landable and revertable:

1. **Delete the dead modules (A):** `ww_agent/src/memory/` (package + README), `runtime/rest.py` +
   the `/world/rest-metrics` route, `runtime/retrieval.py`, `api/game/turn.py` + its router
   registration. Full-stack boot + smoke after each deletion commit.
2. **Keeper triage of the route list (B):** one pass over the ~20 routes marking each
   `delete` / `keep-and-document`. Then delete the confirmed orphans and any service code that becomes
   unreachable; surviving admin routes get a line in `FEDERATION.md` or the engine README so the
   inventory check stays green.
3. **Relocate research tooling (C):** move the probe/analysis scripts to `research/` (pen-swap moves
   as a unit, keeping its `sys.path` shim). Operational scripts stay in `ww_agent/scripts/` —
   candidates to keep at that time: `live_boot.py`, `pulse_familiars.py`,
   `backfill_resident_actor_ids.py`, `familiar.py`. The stay/go split is part of the
   slice's declared scope, decided at execution.
4. **Dissolve `loops/`:** move `doula.py` into `src/runtime/` (rename to what it is — e.g.
   `spawning.py`), update the three import sites (`src/main.py`, `scripts/seed_test.py`,
   `scripts/pen_swap/build_cohort.py`), delete the package and its historical README (coordinate
   with 81).
5. **Alembic squash (after 68/69 land):** 20 migrations including 2 merge-head repairs, several for
   tables that won't survive 68/69. Dev is SQLite-only and Postgres is still ahead — squash to a fresh
   baseline before the Postgres move, tagging the old chain first.

## Files Affected

- Delete: `ww_agent/src/memory/` (entire package), `ww_agent/src/runtime/rest.py`,
  `ww_agent/src/runtime/retrieval.py`, `worldweaver_engine/src/api/game/turn.py`
- Modify: `worldweaver_engine/src/api/game/world.py`, `.../api/game/state.py` (orphan-route
  removal per triage), `.../api/game/__init__.py` (router deregistration), `main.py` (if needed)
- Move: most of `ww_agent/scripts/*` → `research/` (exact stay/go list at slice 3);
  `ww_agent/src/loops/doula.py` → `ww_agent/src/runtime/` (+ 3 import sites); delete
  `ww_agent/src/loops/`
- Later: `worldweaver_engine/alembic/versions/*` (squash), `alembic.ini` untouched
- Tests covering deleted surface: remove alongside their subjects (e.g.
  `tests/service/test_storylet_ingest.py` goes with 69's file, per whichever major deletes it first)

## Acceptance Criteria

- [ ] `grep -rn "src.memory\|runtime.rest\|runtime.retrieval" ww_agent --include='*.py'` returns only
      hits inside `src/runtime/memory.py` itself (no package references)
- [ ] Route inventory re-run: every remaining `@router.*` path has a named consumer (client, agent,
      federation peer, script) **or** a documentation line
- [ ] `ww_agent/src/loops/` no longer exists; spawn orchestrator imports from `src.runtime.*`
- [ ] `ww_agent/scripts/` contains only operational tooling; research probes run from `research/`
- [ ] `python scripts/dev.py check` green; `cd ww_agent && python -m pytest tests/ -v` green
- [ ] Full-stack smoke: `weave-up --city ww_sfo`, resident awakens, client entry flow works, no
      import errors in engine or agent logs
- [ ] (slice 5) Fresh clone migrates from empty DB to head on the squashed baseline

## Risks & Rollback

- **Lazy-import false negatives** (something dynamic the grep missed): mitigated by small per-module
  deletion commits + full-stack smoke after each; rollback is a single `git revert`.
- **A "dead" route was a keeper-curl tool:** the triage slice gates every route deletion on an explicit
  keep/delete call; the failure mode is documentation, not data loss.
- **Script relocation breaks muscle memory / shard cron:** grep shard compose files and `.claude`
  configs for script paths before moving; leave a one-line README pointer in `ww_agent/scripts/`.
- **Alembic squash strands an existing shard DB:** tag the pre-squash chain (`alembic-pre-squash`),
  document the "upgrade to old head first, then switch" path; shard DBs are local/regenerable at this
  stage.
