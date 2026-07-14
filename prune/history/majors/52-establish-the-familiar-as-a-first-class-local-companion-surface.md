# Establish the familiar as a first-class local-companion surface

> **Canonical home: WorldWeaver (2026-07-14).** Migrated in full from the legacy `the-stable`
> work-item ledger during the one-resident/many-worlds consolidation. In this record, “familiar” names
> a resident inhabiting a keeper-tended hearth; it is not a separate agent species (Major 86).

> **Disposition: superseded; archived 2026-07-14.** This item succeeded in making the hearth embodiment
> real, but its category boundary is now rejected: a familiar is a resident at home. Major 86 owns the
> universal resident/hearth host, Major 55 retains the unfinished native/sight surface, Major 65 owns the
> shared capability ecology, and Major 43 owns the human front door.

## Metadata

- ID: 52-establish-the-familiar-as-a-first-class-local-companion-surface
- Type: major
- Owner: Levi
- Status: in-progress (much built off-harness; this item back-fills hygiene and holds the forward threads)
- Risk: medium
- Target Window: ongoing through Q3 2026 (Tiiny AI Pocket Lab delivery ~Aug 2026)
- Depends On: 49 (substrate + pulse), 50 (persistent local practitioner / kept memory / workshop / drive vector), 51 (own-model path)

## Problem

A large, coherent body of work — the **familiar**: a single WorldWeaver resident run as a persistent desktop companion on the keeper's own machine — was built rapidly and almost entirely **outside the harness**. It now spans:

- `ww_agent/familiar/<name>/` — a stable of **seven** distinct souls×models (Cinder/gemini, Wren/claude-haiku, Skein/deepseek, Gaston/mistral-large, Maker/claude-sonnet-4.5, Hades + Persephone/local qwen, cloud-preview gemma-4b/qwen-7b).
- `ww_agent/src/familiar/local_world.py` — `LocalWorld`, duck-typing the `ww_client` surface so the unmodified `CognitiveCore` runs locally (system-clock grounding, the whisper summon channel, the voice sink, the FileScope read capability).
- `ww_agent/familiar/portrait/` — the browser/Tauri portrait (the breathing ember, felt sense, exchange, workshop + kept rails), `serve.py`, the two-file bridge (`state.json` read / `whispers.jsonl` append).
- `ww_agent/scripts/familiar.py`, `wake.sh`, `wake-all.sh`, `wake-local.sh`, `pulse_familiars.py`.

The vision is Major 50's "persistent local practitioner" made *personal* — a companion you glance at, not a chatbot — and strategically it is the **local-first / commons thesis** (hekswerk / world-weaver.org) in miniature. But because it grew off-harness, the threads are scattered, the experiments are ad hoc, and there is no single authoritative item describing the surface or governing its forward work.

## Proposed Solution

Adopt the familiar surface into the harness as one major, retroactively documenting what exists and governing the remaining threads. The surface has four standing layers — **daemon** (`familiar.py` + `LocalWorld`), **portrait** (the UI + bridge), **capabilities** (FileScope read, workshop write, drive vector, anchor-gating), and **fleet ops** (the wake scripts, model tiering cloud↔local, deployment) — and this item holds the open work across them.

Forward work (each tracked as acceptance criteria or a follow-up minor):

- **Anchor-gating rollout** governed by hit-rate, unblocked by semantic matching (minor 46). Today: Skein/Hades/Persephone gated (≥90% hit, no flood); Gaston reverted (61%, flooded); Wren/Cinder/Maker held.
- **Model tiering** cloud-preview ↔ true-local, made clean (the `cloud_model` field + `--model` override exist; the lanes — `wake-all` vs `wake-local` — are split by the `local` flag).
- **Deployment**: point `wake-local` at the **Pocket Lab** (OpenAI-compatible) when it ships — a one-line URL swap; and a stable **named tunnel** (`familiar.world-weaver.org` behind Cloudflare Access) to replace ephemeral quick tunnels.
- **Portrait polish**: render thin "·" journal beats as a quiet mark; live-refresh relative timestamps; carry the "answers in its own way" disclaimer through to public copy.
- **Tooling**: formalize the diagnostic scripts (`field_guide.py`, `_baseline_retrieval.py`, `_overnight_check.sh`) from scratch into kept tools; add `sync-bundle.sh` (minor 49).

## Files Affected

- `ww_agent/familiar/` (the stable, the portrait, the wake scripts)
- `ww_agent/src/familiar/local_world.py`, `ww_agent/src/familiar/file_scope.py`
- `ww_agent/scripts/familiar.py`, `ww_agent/scripts/field_guide.py`, `pulse_familiars.py`
- `ww_agent/src/runtime/` (shared substrate — touched only via the capability-scoping seam, never forked)

## Non-Goals

- No fork of the substrate. The familiar runs the **unmodified** `CognitiveCore`; LocalWorld duck-types the client and any divergence (e.g. capability scoping) is a declared seam, not a parallel mind.
- No guild / apprentice-in-public surface here — that is Major 50/44's shard-resident domain. The familiar is the *private companion* cut.
- No behavior scripting (the Dwarf Fortress law): the familiar's voice, acts, and making must stay emergent.

## Acceptance Criteria

- [ ] A single authoritative item (this) describes the familiar surface; the off-harness work is documented, not just lived.
- [ ] Anchor-gating is governed by a measured hit-rate policy, not per-model guessing (depends on minor 46).
- [ ] `wake-all` (cloud) and `wake-local` (Ollama / Pocket Lab) lanes are clean; no familiar runs in both at once; no stale-daemon double-writes to one `state.json`.
- [ ] The portrait survives reload, shows delivery status, allows copy/selection, and the kept-log is newest-first with timestamps + full history. (DONE 2026-06-04.)
- [ ] A documented path exists to run the whole stable locally on the Pocket Lab with zero token egress.

## Validation Commands

- `cd ww_agent && ../worldweaver_engine/.venv/bin/python -m pytest tests/ -q`
- `cd ww_agent && ../worldweaver_engine/.venv/bin/python scripts/field_guide.py` (internal-state read across the stable)
- `node --check ww_agent/familiar/portrait/ui/app.js`

## Pruning Prevention Controls

- Authoritative path for touched behavior: `ww_agent/src/runtime/` (substrate, unmodified) + `ww_agent/src/familiar/` (the local world + read capability). The portrait is a pure view over the two-file bridge.
- Parallel path introduced: none. LocalWorld is a duck-typed adapter to the same `CognitiveCore`, not a second runtime.
- Optional/harness behavior on default path: capability scoping (`muted_self_senses`) is opt-in per world; the real `WorldWeaverClient` declares none → shard residents unchanged.
- Generated artifacts + archive target: per-familiar runtime (`memory/`, `workshop/`, `state.json`, `whispers.jsonl`, `voice.jsonl`) is gitignored; the architecture-bundle is a synced mirror of `src` (minor 49).
- Flag lifecycle: `anchor_gating` (per-familiar, default off), `local` (per-familiar), `cloud_model` (per-familiar) — all read at daemon boot; retire none until the semantic-matching fix (46) makes gating safe by default.

## Risks and Rollback

Risks:

- Off-harness drift recurs if forward familiar work skips this item.
- Capability-scoping or gating seams leak into shard-resident behavior.

Rollback:

- Each capability is a per-familiar flag; clearing it returns the familiar to expressive-only. The substrate is untouched, so disabling the familiar surface is just not running the wake scripts.

## Follow-up Candidates

- minor 46 (semantic anchor matching — unblocks gating), 47 (cost evidence), 48 (chronotype hygiene), 49 (sync-bundle)
- Pocket-Lab deployment runbook (create when hardware ships)


---

## Progress addendum 2026-06-04 — companion-surface hardening + the first file-grounded familiar

A long off-harness session landed a run of substrate/companion fixes (all committed to the
familiar runtime; familiar configs tracked, the harness is private). Logged here under 52
because it is all "make the familiar a thing someone could actually live with."

**Shipped (commits):**
- `e25598a` / `284ba6f` — Maker re-scoped to read every peer's full life (souls + workshops),
  not just a soul-doc; the peer-read ("who you live alongside") now works. read_roots ordering
  is load-bearing (peer dirs before the repo root; the nested-root match rule).
- `0615a4c` — FileScope reach hint surfaces directories first, so the folders worth navigating
  into (identity/, workshop/, src/) appear ahead of runtime-log files.
- `1037e81` — FileScope: open a read-root folder by name (Mason was stuck on `read <folder>/`
  → not_found; the folder-listing path was unreachable). Browsing works now.
- `4a2cc93` + `6e66048` — mute mobility_drive for hearth familiars (a "walk the map" drive with
  no map). NOTE: 4a2cc93 was a regression — it dropped the muted sense from the prediction only,
  so a sense whose stimulus still fires (mobility) surprised at full delta every tick and pumped
  arousal stack-wide; `6e66048` fixes it (mute now drops from the stimulus too).
- `254f84e` — drop the phantom "curiosity" drive_nudges example (it was only ever a schema
  example the pulse copied into a self-reinforcing fake drive). Piloted on Maker (per-familiar
  `clean_drive_nudges`); confirmed live (Maker is the only familiar with no curiosity affect).
- `64ae38e` — **canon**: optional `identity/canon.md` of immutable ground-truth facts, injected
  into the system prompt under a guard frame ("a contradiction — even one the keeper says about
  themselves — belongs to someone else, not a change in you"). The identity anchor.
- `55beaee` — per-familiar ignition refractory (`refractory_seconds`): caps the conversational
  echo / self-paraphrase a hot talker emits between the keeper's turns; force_ignite bypasses it
  so a whisper always gets an instant reply. Wren set to 120s.

**The first file-grounded familiar — Mason Kirsch (mk-2026).** A simulated Hekswerk relocation
client given a soul (adapted from the keeper's own persona prompt) + FileScope read_roots scoped
to exactly his three client folders (the persona's information boundary, now enforced in code —
practitioner-internal notes return outside_scope). Demonstrated the new failure mode AND its fix:
he absorbed the keeper's own relocation (DAFT/Netherlands) into his self-model against his files
(Blue Card/Berlin), it was surgically remediated (kept-memory + ledger keepsakes + journal +
projections + corrective whisper), the canon was built to prevent recurrence, and a provocation
test (re-misattribute DAFT to him) confirmed the canon HELD — he corrected the keeper and kept
no corrupt fact. Verdict: prompt-level canon sufficient; no hard keepsake-gate (v2) needed yet.

**Open forward threads:**
- Re-measure Mason's anchor gating CLEAN after the next wake (the mobility regression confounded
  his arousal; if still hot at a ~17% hit-rate, revert his gate).
- Mason is a refractory candidate too — he echoes in *journals* (re-journaled one realization 7×).
- FileScope multi-root nav papercut: a familiar can't reach a *sibling* root by a verb-laden path
  ("read received-from-client/mason-running-notes.md" when it lives in the mason-memory root).
- Roll `clean_drive_nudges` to the rest of the stable after observing Maker's before/after.
- Canon held on ONE test (Sonnet, and the canon pre-named DAFT) — a phase-3 generalization test
  (a contradiction the canon doesn't pre-name) would prove the guard generalizes, if wanted.
- "Files anchor identity" could grow from prompt-level canon into a real invariant (a familiar may
  learn and change, but not accrue a self-belief that contradicts its read-only canon).
