# Extract and remove all guild reference and affordances

## Update (2026-07-12) — slices 3–5 executed: the demolition is COMPLETE

Executed on branch `major-68-slice-3-guild-backend`, using the Major 83 route audit as evidence
(post-slice-2, all 15 guild/adaptation/social-feedback routes had **zero callers anywhere**).

- **Slice 3 (backend API + services):** all 15 routes deleted from `api/game/state.py` — the
  guild-profile/social-feedback/adaptation/guild-quests state routes and the `/guild/*` board,
  quest, starter-pack, steward, and governance surface — plus their 8 request models and 16
  guild-internal helpers (board serialization, quest assignment normalization, governance
  capabilities). `guild_service.py` (608 lines) and `starter_quests.py` deleted whole.
  **Disambiguation that mattered:** `growth_service.py` is NOT guild — it is the identity-growth
  concordance gate (live; agents post to `/state/{}/identity-growth`) — untouched. Likewise
  `settings.enable_runtime_adaptation` gates *narrative* adaptation in `llm_service` (naming
  collision only) — untouched.
- **Slice 3b (reporting/exports):** `scripts/export_branch_training_traces.py` deleted (existed
  to export guild-labeled traces). `daily_world_digest.py`: `_build_guild_watch` (196 lines)
  replaced by a compact `_build_growth_watch` — the identity-growth proposal counts were the one
  non-guild tenant and now render under **Identity**; the publication renamed
  "Guild of the Humane Arts Morning Brief" → "WorldWeaver Morning Brief".
- **Slice 4 (data layer):** the four ORM classes (`GuildMemberProfile`, `SocialFeedbackEvent`,
  `RuntimeAdaptationState`, `GuildQuest`) deleted; forward migration `d7e2f9a1c4b8` drops the
  four tables (guarded) with a faithful-recreation downgrade. Round-tripped on a fresh DB
  (upgrade → tables gone; downgrade → all four back; re-upgrade clean).
  `resident_identity_growth.growth_proposals` — added by the same historical migration but the
  live identity mechanism — intentionally untouched.
- **Slice 5 (docs/souls):** already clean. The `prune/ROADMAP.md` guild mention is the
  *retirement rationale* under the Dwarf Fortress law (deliberate history — stays). The
  `substrate_sync_manifest.toml` entry for `src/runtime/guild.py` classifies **the-stable's**
  copy, which still exists there — its fate belongs to Major 76's reconvergence. No resident
  soul/template carries guild references.
- **Validation:** engine suite 705 passed; app boots with 61 routes and zero guild survivors;
  14 guild endpoint tests deleted with their subjects; digest test rewired to `growth_watch`.

Historical `alembic/versions/*guild*` migrations remain as immutable history (per the 2026-06-16
note below); Major 83 slice 5's squash will fold them into a fresh baseline once this lands.

## Update (2026-06-21) — execution begun; a behavior-shaping tentacle found in the agent runtime

Demolition started, leaf-first across the whole system (both clients consume the backend guild API).

- **Slice 1 shipped (commit c78fe37):** the entire guild/quest surface removed from the React client —
  GuildBoard/GuildShell/GuildQuestPanel + hooks, the API methods/types, the `.ww-guild-*` CSS, and the
  participation selector collapsed `observer|mentor_board|participant → observer|participant`
  (`GuildAccessMode → ParticipationMode`, key `ww.client.participation_mode`). Guild-coupled steward
  bootstrap removed; steward witness-surface deferred to Major 71. Verified end-to-end with a headless
  browser (observer entry writes the new key; no Guild tab; legacy storage inert).

- **Finding — the economy has a reward-shaping arm wired into the agent cognitive runtime.**
  `ww_agent/src/runtime/guild.py::apply_runtime_adaptation` pulls guild **social-feedback**
  `behavior_knobs` (`social_drive_bias`, `proactive_bias`, `mail_appetite_bias`, `quest_appetite_bias`,
  …) and **mutates the resident's live `LoopTuning`** (`fast_proactive_seconds`, `fast_cooldown_seconds`,
  `fast_act_threshold`, `mail_send_delay_seconds`) keyed by `source_feedback_ids`. It is called on every
  resident via `resident.py::_hydrate_guild_state()` (on awaken) and `_sync_guild_state()` (every 180s).
  This is **precisely the Dwarf-Fortress-law violation the major exists to kill** — an external/guild
  feedback signal reaching in to shape the mind's behavior — and it is **doubly obsolete**: it operates
  on the loop-era `fast_*` tuning that Major 49 demoted to mechanism. The `runtime_*_bias` overlay fields
  and `identity.{guild_profile,guild_quests,runtime_adaptation}` (`identity/loader.py`) are **write-only
  dead** — nothing in the substrate reads them; the loader does not parse them from disk.

- **Revised slice plan (sequencing: agent-runtime first — consumer before provider):**
  1. ✅ React client. 2. **Agent runtime decouple** — delete `runtime/guild.py`; strip
  `_hydrate_guild_state`/`_sync_guild_state`/`_authored_tuning` from `resident.py`; remove the
  guild/social/adaptation methods from `world/client.py`; drop the dead `runtime_*_bias` + guild fields
  from `identity/loader.py`. 3. Backend API + services (`api/game/state.py` endpoints incl.
  `/adaptation` + `/social-feedback`; `guild_service.py` incl. `derive_runtime_adaptation`;
  `starter_quests.py`; response schemas; tests). 4. ORM models + forward Alembic drop migration.
  5. Resident soul/identity backstory + VISION/ROADMAP/docs purge.

## Update (2026-06-16) — still unexecuted; current live surface confirmed

Re-confirmed during the public-repo cleanup pass: this demolition has **not** been executed. A fresh grep
found the live guild surface still present in the React client — `GuildBoard.tsx`, `GuildQuestPanel.tsx`,
`GuildShell.tsx`, with wiring in `App.tsx`, `AppTopbar.tsx`, `WorldActionPane.tsx`, and `wwClient.ts` — plus
the historical alembic `*guild*` migrations (immutable history; leave). The stale `reports/guild_posts/`
artifacts were removed in the cleanup pass; everything below remains to do.

## Decision and lineage

The guild reputation/quest economy is **retired** — named a Dwarf-Fortress violation
(authored economy of fake consequences / reward shaping) and killed. The human layer is
**not** guilds; it is the steward witness-surface + the player-shadow. This major does the
demolition that the retirement decision implies but no prior major scheduled: extract and
remove guild/quest/apprentice affordances from the live runtime, API, frontend, schema, and
seed material.

- **Supersedes / closes:** major 44 (guild contribution surfaces), major 45 (quest
  evidence/completion), minor 43 (guild-watch digest), minor 44 (human quest commons). Those
  built or refined the surface this major removes.
- **Spares `steward`:** the steward witness-surface and player-shadow are the *replacement*
  for the guild human-layer — do NOT remove steward affordances. Guild ≠ steward.
- **Status:** proposed (2026-06-08, keeper's call). Removal/extraction work; cold repo (no
  live runtime to preserve), so the hand is free.

## Problem

Guild and quest machinery is still wired throughout the codebase even though the economy it
serves is retired. A reference grep (2026-06-08, excluding `.git`, archives, `history/`)
finds **~29 files containing `guild`**, concentrated in:

- `worldweaver_engine/src/services` (16) — the guild/quest service layer
- `worldweaver_engine/client/src/components` + `hooks` (15) — guild board / quest UI
- `worldweaver_engine/src/api/game` (9) — guild/quest endpoints
- `ww_agent/src/runtime` (7) — runtime references (incl. the loop-era evidence reducer)
- `worldweaver_engine/scripts` (7) and `worldweaver_engine/alembic/versions` (4) — tooling +
  **DB migrations** that created guild/quest tables
- a handful of resident **soul/identity docs** (e.g. `ww_agent/residents/*/identity`) that
  name guild membership as backstory

Left in place, this is dead weight that (a) re-suggests guilds as a live affordance to any
fresh agent or resident, (b) carries quest-completion code paths that depend on the demoted
loop architecture (`ww_agent/src/loops/slow.py`, retired by Major 49), and (c) keeps schema
and endpoints for a product surface that is no longer the target.

> Scope caveat: the `quest` token also matches `question`/`request`; the precise removable set
> must be confirmed with a word-boundary / identifier-level grep during execution, not the
> raw substring count.

## Proposed Solution

Remove in dependency order — frontend → API → services → runtime → schema → seed — so nothing
references a thing that's already gone.

1. **Frontend.** Delete guild/quest components and hooks (`GuildBoard.tsx`, quest panes,
   `WorldInfoPane` guild sections, guild hooks); remove their routes/menu entries; excise
   guild props threaded through the app shell.
2. **API.** Remove guild/quest endpoints under `src/api/game`; drop their routers/registration.
3. **Services.** Delete the guild/quest service modules in `src/services`; remove imports.
4. **Runtime.** Remove guild/quest handling in `ww_agent/src/runtime` and the quest-evidence
   reducer path (already orphaned by Major 49's loop demotion).
5. **Schema.** Add a forward Alembic migration that drops the guild/quest tables; leave the
   historical creation migrations in place (history is immutable) but ensure head is clean.
6. **Seed / souls.** Review the resident identity docs that mention guild membership; rewrite
   the backstory to remove the guild affordance **without** flattening the character (a
   judgment edit per soul, not a blind delete — souls are canonical, handle with care).
7. **Docs.** Purge guild/quest from VISION/ROADMAP/product packs and any agent-facing docs so
   nothing re-advertises it.

## Files Affected

(Indicative — confirm the exact set via grep at execution.)
- `worldweaver_engine/client/src/components/GuildBoard.tsx`, quest/guild panes, `WorldInfoPane.tsx`
- `worldweaver_engine/client/src/hooks/*` (guild/quest hooks), app-shell wiring
- `worldweaver_engine/src/api/game/*` (guild/quest routes)
- `worldweaver_engine/src/services/*` (guild/quest services, ~16 files)
- `worldweaver_engine/src/models/*` (guild/quest models)
- `worldweaver_engine/alembic/versions/*` (new drop migration; keep historical create migrations)
- `worldweaver_engine/scripts/*` (guild/quest tooling/seeders)
- `ww_agent/src/runtime/*`, `ww_agent/src/loops/slow.py` (quest-evidence reducer path)
- `ww_agent/residents/*/identity/*` (soul backstory edits, per-resident judgment)
- `prune/VISION.md`, `prune/ROADMAP.md`, product/talking-point docs

## Acceptance Criteria

- [ ] No `guild`/`Guild`/`GUILD` identifier remains in live `src` (engine + agent), frontend,
      or API — verified by a word-boundary grep returning zero outside `history/`, archives,
      and immutable historical migrations.
- [ ] No quest/apprentice affordance remains in the runtime, API, or UI (word-boundary grep;
      excludes `question`/`request` false matches).
- [ ] A forward Alembic migration drops the guild/quest tables; `alembic upgrade head` is clean
      on a fresh DB; historical create-migrations are untouched.
- [ ] Resident identity docs no longer assert guild membership; each edited soul still reads as
      a coherent character (per-soul review, not bulk delete).
- [ ] `steward` witness-surface and player-shadow affordances are intact and untouched.
- [ ] VISION/ROADMAP/product docs no longer advertise guilds or quests.
- [ ] `python scripts/dev.py quality-strict` green; targeted tests for removed surfaces deleted
      or repointed; no dangling imports.

## Risks & Rollback

- **Hidden coupling.** Guild/quest code may be imported by surfaces you intend to keep (world
  info, scene). Remove leaf-first (frontend → API → services) and let the type-checker/tests
  surface dangling references before deleting shared modules.
- **Schema irreversibility.** Dropping tables is destructive to any existing data. The repo is
  cold (no live data to preserve); still, do it as a normal forward migration with a documented
  down-path, and snapshot the DB first if any instance holds real rows.
- **Soul damage.** Over-aggressive identity edits can flatten a resident. Treat soul docs as
  canonical; edit the guild line, preserve the person. If unsure, leave the soul and flag it.
- **Rollback** is git (the removal is a reviewable diff) plus the legacy bundles in
  `worldweaver_artifacts/legacy_git_bundles/`. No parallel guild rail is kept.

---

*Created 2026-06-08. Executes the guild-economy retirement decision (Mr. Review round-1; the
guild-retired standing decision). Closes majors 44/45 and minors 43/44. Spares steward.*
