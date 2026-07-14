# Remove storylet, turn-pipeline, and world-bible machinery

## Completion (2026-07-14) — archived

Major 69 is complete. Three final commits finished the coordinated slice without orphaning the world
ledger:

- `058dee1` separated the reusable action interpretation, validation, narration, and choice helpers from
  the obsolete turn package.
- `066ae7f` replaced the 2,821-line turn orchestrator with a focused action-submission service built on
  the canonical `WorldEventCommand` contract.
- `2e884f2` removed the remaining narrative-turn compatibility, dead prompts and schemas, the dormant
  feature flag, and the obsolete `world_events.storylet_id` column through forward migration
  `6a9d3e2f1b70`.

The public `/api/action` and idempotency contracts remain intact. Action, movement, public speech,
bootstrap, and system events retain canonical ledger writes; `WorldProjection` remains a reducer-produced
materialized view. Private DMs deliberately remain outside public `WorldEvent` history pending the
visibility-aware relational envelope in Majors 66/72.

Final evidence:

- live engine/client/agent source grep is zero for storylet, world-bible, `turn_service`, and the removed
  pipeline flag outside immutable migrations and history;
- `alembic upgrade head` succeeds on a fresh SQLite database and the resulting `world_events` table has no
  `storylet_id` column;
- `worldweaver_engine/.venv/bin/python scripts/dev.py check`: green, including 475 engine tests plus client
  typecheck/build;
- `ww_agent/.venv/bin/python -m pytest tests -q`: 268 passed, 1 skipped.

## Earlier update (2026-07-14) — canonical event spine foundation landed; deletion still pending

Five bounded commits established and exercised the replacement boundary before deleting turn code:

- `45a20d5` added typed `WorldEventCommand` / `WorldEventReceipt` submission with validation,
  reducer support, projection receipts, and exact rollback tests.
- `eedf17e` routed session bootstrap, map movement, and public speech through it; bootstrap is now an
  approved event type rather than an unembedded direct ORM insert.
- `08ba8f5` removed every production `record_event()` call outside the submission service.
- `daf3c3d` made simulation-tick reduction + persistence atomic where those phases are adjacent.
- `455cb5a` added prepared reduction/commit for `/api/action`, fixed two shallow-snapshot rollback bugs,
  and proved that narration failure restores state and writes no event.

The engine suite is green at **476 passed**. The public `/api/action` request/response and idempotency
contracts are unchanged. `turn_service.py`, `src/services/turn/`, and the dormant
`WW_ENABLE_UNIFIED_TURN_PIPELINE=false` duplicate path still exist; their deletion is the next slice and
has not been mixed into the ownership migration.

Private DMs intentionally remain in `DirectMessage`, not `WorldEvent`: world history exposes event rows.
Major 66/72 must supply a relational envelope with explicit private visibility before mail joins a common
event contract. Do not satisfy event unification by leaking message content into public history.

## Update (2026-07-13) — slices 1-2 executed; turn-pipeline (slice 3) DEFERRED

Executed on branch `major-69-slices-1-2-storylet-demolition` (commit ada2bd0, −11,487 lines).
Keeper choice: land the storylet demolition now, pause before the /action rework.

- **Slice 1 — /api/next removed.** Confirmed orphaned (client + agent act through /api/action;
  `POST /next` had no production caller). Deleted story.py, the next-turn orchestration adapter,
  `wwClient.postNext`, the agent's `post_next`, `scripts/eval_narrative.py`, and the
  `narrative-eval-smoke` CI workflow (keeper approved deleting the eval — it measured the deleted
  pipeline; `ci-gates.yml` remains the gate).
- **Slice 2 — storylet engine + world-bible removed.** 7 service modules deleted (game_logic,
  storylet_selector/utils/ingest, semantic_selector, prefetch_service, seed_data); `render()`
  moved to `turn/narration.py`, `DEFAULT_SESSION_VARS` to `session_service`; startup seeding
  dropped (world content is city-pack only, keeper-confirmed). llm_service gutted 2609→455 lines
  (storylet/bible/beat generators gone). Client prefetch chain removed. `Storylet` model deleted;
  forward migration `e8b3a6d2f1c9` drops the table (round-tripped on a fresh DB with `WW_DB_PATH`
  set — env.py ignores the alembic cfg URL). 22 orphaned config flags + `storylet_count` schema
  fields removed. **world-bible: confirmed no generator remains** (acceptance criterion met).
- **Coordinating finding — the turn pipeline still writes events, so it stays (for now).** Rather
  than delete `turn_service.py` before the #29/#66 event-path unification, slice 2 **stubbed its
  storylet hooks to no-ops** (pick/find/adapt/ensure → None; the JIT-beat persister → no-op). The
  pipeline still serves `/api/action` with an unchanged response contract (31 action tests green),
  and still owns the event-ledger write. This satisfies the major's hard gate ("do NOT delete
  turn_service in isolation") by keeping it alive until the event contract is unified.

**Remaining — slice 3 (turn-pipeline removal), NOT started, gated on #29/#66:** rework `/api/action`
into a lean interpret→validate→reduce→record path that writes events through the unified contract,
then delete `turn_service.py` + `src/services/turn/` and the stubs. Also remaining: the internal
`NextReq`/`NextResp`/`ChoiceOut` schemas survive only because `turn_service` still builds them —
they go with slice 3. Sequence #29/#66 + slice 3 as one change set.

## Decision and lineage

The old simulation mechanics — the storylet engine, the per-turn narration pipeline, and the
world-bible seed-enrichment layer — are **not the target anymore**. The resident mind is the
mechanistic substrate + predictive pulse (Major 49); narration-by-storylet and the turn
pipeline are loop-era apparatus. This major exists to ensure these are **actually removed, not
merely disconnected** — dead code that still describes a storylet/turn-narration model
re-suggests it to any fresh agent.

- **Closes:** major 10 (prune storylet pipeline), major 16 (decompose turn pipeline), major 31
  (demote world-bible). Those described or refined machinery this major deletes.
- **Coordinates with:** major 29 (normalize world-event submission) and major 66 (log edges,
  not nodes) — the turn pipeline (`turn_service.py`) is also the path #29 is trying to unify.
  Removing it must not orphan the event ledger; do the event-path consolidation (#29/#66) and
  the turn-pipeline removal as one coordinated change, not two that fight.
- **Status:** complete and archived (2026-07-14).

## Problem

Reference grep (2026-06-08, excluding `.git`, archives, `history/`):

- **storylet: ~45 files** — concentrated in `worldweaver_engine/src/services` (17) +
  `src/services/turn` (5), `scripts` (5), `alembic/versions` (5, DB tables), `src/api/game`
  (4), `ww_agent/src/world` (2), models (2). A live, load-bearing subsystem.
- **turn-pipeline: `turn_service.py`** (+ `src/services/turn/`) — the per-turn intent→reducer→
  narration→record_event flow. Major 29 documents that other surfaces *bypass* it
  inconsistently; in the Major 49 substrate+pulse model there is no per-turn LLM narration.
- **world-bible: 0 hits** — appears **already removed** (no `world_bible`/`WorldBible`/`world
  bible` references remain). This major only needs to **confirm** it's gone and sweep any
  renamed stragglers (e.g. seed-enrichment flavor text), not rebuild a deletion already done.

Left in place, this machinery is dead weight tied to the retired loop/turn model, carries DB
tables and scripts no longer exercised, and muddies the engine contract #29/#66 are clarifying.

## Proposed Solution

1. **Confirm world-bible is gone.** Word-boundary grep for world-bible / seed-enrichment-flavor
   identifiers; remove any straggler; if truly absent, record "already removed" and move on.
2. **Storylet removal**, leaf-first: frontend/API references → `src/services` storylet modules
   + `src/services/turn` storylet hooks → models → a forward Alembic migration dropping
   storylet tables (keep historical create-migrations). Remove storylet scripts/seeders.
3. **Turn-pipeline removal — COORDINATED with #29/#66.** Do NOT delete `turn_service.py` in
   isolation: first land the unified canonical event-submission contract (#29) so map/chat/
   action all write events through one path; once nothing depends on the turn pipeline's
   record_event call, remove `turn_service.py` + `src/services/turn/`. Sequence the two as a
   single change set.
4. **Sweep agent side.** `ww_agent/src/world` + memory references to storylets/turn-narration.

## Files Affected

(Indicative — confirm exact set via word-boundary grep at execution.)
- `worldweaver_engine/src/services/*` (storylet modules, ~17), `src/services/turn/*`
- `worldweaver_engine/src/api/game/*` (storylet/turn endpoints)
- `worldweaver_engine/src/models/*` (storylet models)
- `worldweaver_engine/alembic/versions/*` (forward drop migration; keep historical creates)
- `worldweaver_engine/scripts/*` (storylet seeders/tooling)
- `ww_agent/src/world/*`, `ww_agent/src/memory/*` (agent-side references)
- coordinate with whatever #29/#66 touch for the event-path consolidation

## Acceptance Criteria

- [x] No `storylet`/`Storylet` identifier remains in live `src` (engine + agent), API, or UI —
      word-boundary grep returns zero outside `history/`, archives, immutable migrations.
- [x] world-bible confirmed absent (grep zero); any straggler removed; "already gone" recorded
      if nothing was found.
- [x] The per-turn narration pipeline (`turn_service.py` / `src/services/turn`) is removed
      ONLY after world-event submission is unified (#29/#66); no surface loses its event-ledger
      write in the process.
- [x] Forward Alembic migration drops storylet (and any turn-pipeline-only) tables; `alembic
      upgrade head` clean on a fresh DB; historical create-migrations untouched.
- [x] `python scripts/dev.py check` green; tests for removed surfaces deleted/repointed;
      no dangling imports.

## Risks & Rollback

- **Turn-pipeline is load-bearing for events.** Deleting it before #29/#66 unify the event
  paths would orphan map/chat/action event writes. Hard-gate: event consolidation lands first.
- **Storylet coupling.** Storylet code may be imported by surfaces being kept (scene/state).
  Remove leaf-first; let the type-checker/tests surface dangling refs before deleting shared
  modules.
- **Schema irreversibility.** Dropping tables is destructive; repo is cold (no live data), but
  do it as a normal forward migration with a documented down-path; snapshot any DB with real rows.
- **Rollback** is git + the legacy bundles in `worldweaver_artifacts/legacy_git_bundles/`.

---

*Created 2026-06-08. Completed and archived 2026-07-14. Closes majors 10/16/31. Coordinated
turn-pipeline removal with the #29/#66 event-submission unification so the world ledger was never
orphaned.*
