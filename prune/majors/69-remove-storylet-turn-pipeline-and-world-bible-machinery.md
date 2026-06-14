# Remove storylet, turn-pipeline, and world-bible machinery

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
- **Status:** proposed (2026-06-08, keeper's call). Removal work; cold repo.

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

- [ ] No `storylet`/`Storylet` identifier remains in live `src` (engine + agent), API, or UI —
      word-boundary grep returns zero outside `history/`, archives, immutable migrations.
- [ ] world-bible confirmed absent (grep zero); any straggler removed; "already gone" recorded
      if nothing was found.
- [ ] The per-turn narration pipeline (`turn_service.py` / `src/services/turn`) is removed
      ONLY after world-event submission is unified (#29/#66); no surface loses its event-ledger
      write in the process.
- [ ] Forward Alembic migration drops storylet (and any turn-pipeline-only) tables; `alembic
      upgrade head` clean on a fresh DB; historical create-migrations untouched.
- [ ] `python scripts/dev.py quality-strict` green; tests for removed surfaces deleted/repointed;
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

*Created 2026-06-08. Closes majors 10/16/31. Coordinates turn-pipeline removal with the
#29/#66 event-submission unification so the world ledger is never orphaned.*
