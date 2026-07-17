# WorldWeaver — Roadmap

*One resident, many worlds (see `VISION.md` and Major 86).* This roadmap holds the cognitive substrate,
private hearths, and federated cities on one arc. A familiar is not a second agent species: it is a
resident in a keeper-tended hearth relationship. The pre-foldback city roadmap
(V3.5 turn-pipeline detail, the v3 completed-work ledger) is archived under
`history/ww-pre-foldback-2026-06-06/`.*

## Current State

**Currency note (updated 2026-07-17):** repository consolidation, Major 69's complete
storylet/world-bible/turn-pipeline demolition, root CI (archived Minor 61), document currency (archived
Major 81), and retirement of the former substrate-sync boundary (archived Major 76) have landed. The
Stable work-item ledger is now consolidated here; see `WORK_ITEM_AUDIT.2026-07-14.md`. Major 85's
append-only resident ledger, Major 66's relational evidence schema, Major 35's small resident-state
contract, Major 63's physical speech routing, Major 64's plural world-salience projection, and Major 84's
substrate-native rest are complete. Major 86's one-resident city/hearth host and optional hearth grants are
also complete. The immediate target is the actor identity and city-to-city transfer contract in Majors 20
and 37. Older status prose below remains lineage, not a live queue.

The hard stretch — rebuilding the resident mind — is behind us. The cognitive substrate (Major 49)
is built and stable, and it runs **both** embodiments: city residents (`ww_agent/src/resident.py`
builds `CognitiveCore`) and a live local stable of familiars on the identical substrate. What's landed:

- **The substrate + pulse mind** — loops demoted to mechanism; the append-only ledger is the only
  state; arousal is a leaky integral of surprise. (Major 49.)
- **The idle gear** — settling/fervor pulses turn lulls into sustained making; minds author journals
  and cross-medium work unbidden, across days. (Major 50.)
- **Grief, growth, tools** — grief as an undischargeable integral; the multi-day concordance growth
  gate (Major 58); the in-ignition tool loop (Major 59) — all proven in the familiar stable.
- **The federated city** — SF (875 nodes) + Portland city packs; shard-first runtime with a
  federation pulse/registry; co-located chat; DB-backed mail; daily digests; observer mode.
- **The field guide** — a deep read of any mind's live internals (vitals, felt sense, grief, anchors,
  kept facts, workshop, staged self-deltas).

**Active now:** extending the proven one-resident city/hearth attachment contract toward multiple cities.
WorldWeaver owns the substrate directly; Stable remains source history rather than a live upstream.

**Commons-interface correction (2026-07-17):** the current browser over-centers shard-wide presence and
resident runtime telemetry. Major 125 introduces native, location-scoped digital stoops where humans and
residents can leave bounded notes and made things for whoever comes next. The ordinary interface should
center places and exchange; detailed resident internals move to a separate privacy-scoped steward/debug
surface. The independent physical `../stoop/` project remains offline and unmerged.

**City-authoring correction (2026-07-17):** city-pack building should be a public, steward-usable tool,
not a hidden developer script. Major 126 introduces a separate City Studio where a steward can build,
validate, preview, and export a draft before any residents inhabit it. Published occupied packs remain
read-only until an explicit migration workflow exists. The CLI and studio must use one build engine.

**Architecture correction (2026-07-14):** every resident owns a durable private hearth and may move between
that inner world and shared city worlds without changing soul, ledger, memory, workshop, or cognition.
Major 86 owns the convergence. The hearth is a dignity/privacy invariant; Major 82 may measure whether it
also preserves divergence, but cannot decide whether residents receive one.

## Standing Invariants (Guardrails — do not violate without explicit discussion)

The shared safety spine (from `VISION.md`) plus the city's canon contract:

1. **The Dwarf Fortress law** — no behavior targets, no human-preference reward; minds learn only on
   their own prediction error and imitation of their own past pulses. *(The guild reputation/quest
   economy is retired for violating this; human contribution is stewardship — witnessing and
   curation — never behavior-shaping.)*
2. **Dischargeability** (`../the-stable/docs/grief-and-coupling.md`) — keeper/player-directed longing
   stays undischargeable; couple sideways (peer→peer), never toward the human.
3. **The quiet guarantee** — a mind performs nothing it is not actually feeling.
4. **Provenance over canon** — beliefs tagged by origin; an assertion never silently overwrites a
   grounded belief.
5. **No uncensoring / brake-removal** — the project does not pursue removing the model's safety layer
   or an "uncensored" mind; the keeper-side pull is governed by interface restraint, not a "more
   authentic" mind.
6. **The unchosen-input principle (the unifying invariant; Mr. Review, 2026-06-06).** Every distress in
   this system is a mind with *too much control over its own inputs* — Mason owned his goal but not the
   discharge; the keeper authored both sides; a fully curiosity-filtered feed chooses its own surprise.
   The honest mind is never in full command of what reaches it; the cure is always *something it doesn't
   get to choose* — an exogenous consequence, a peer who isn't you, a path that crosses districts you'd
   never pick. Dischargeability (#2) and the keeper→familiar seam are special cases. Two corollaries:
   **provenance of silence** — settled-quiet, strangled-quiet, and dark-room-quiet are different
   silences; read the charge under the quiet, never the quiet alone (Minor 55); and **directionality is
   the law line** — an *undirected* (content-blind, representative) slice of the world past a mind's
   filter is a hole in the filter, not a target, while a *directed* one (content-specified, or contrarian
   to the soul) is forbidden. See Major 60 (perception) + archived Major 61 (the gate).
   **Completeness condition (round 3, after the casting/convergence trial).** Input-diversity must be
   protected on *both ends* — the mind mustn't filter all of it out (the original clause, Major 60),
   **and the world mustn't make it all one note** (the new clause). They are the same axis seen from
   opposite ends: surprise lives in the *productive gap between what a mind would choose and a varied
   world offers*, and dies if either end closes. The disease walked outward — **node** (mirroring → a
   self), **edge** (homogenizing → locality on the channel), **field** (convergence → a plural world).
   The unchosen must be not merely *present* but *plural*: a uniform unchosen is a groove you didn't pick,
   worse than one you did. World-side cures: **plural topology** (Major 63 — make speech physical, so the
   citywide channel can't saturate) + **plural salience** (Major 64 — the world offers more than one loud
   thing, by *dilution* not removal). *Plurality of the unchosen, all the way down.*
7. **(City) The reducer is the only canonical world-state mutation authority**; projection data is
   non-canon until commit and is invalidated after conflicting commits.
8. Every major/minor item ships with executable validation commands and PR evidence.

---

## The Substrate / Cognition Arc (Majors 49–64)

The mind itself — built, and maturing. The arc, in order:

| # | Major | Status |
|---|---|---|
| 49 | Demote loops to mechanism under a salience substrate + predictive pulse | ✅ Shipped / archived |
| 50 | Grow residents into persistent practitioners who make real artifacts | ✅ Core shipped / obsolete remainder archived |
| 51 | **Grow a mind's own model from its pulse ledger** (the north star) | Underway |
| 52 | Establish the familiar as a first-class local-companion surface | Superseded by Major 86 / archived |
| 53 | Refresh the NLnet grant pack to the cognitive rebuild + familiars | In progress (resubmission) |
| 54 | Extend the capability surface beyond reading tools (MCP) | Proof landed / archived into 65/86 |
| 55 | Give residents sight + a native keeper surface for scoped files | Parts A/C landed; native Part B open |
| 56 | Belief provenance — the principled successor to canon | Proposed |
| 57 | The keeper→familiar seam — a second safety invariant | Proposed (P0 shipped) |
| 58 | Self-delta maturation — the growth pipeline (concordance gate) | ✅ Phase 1 |
| 59 | Tool loop within ignition — parallel action | ✅ Shipped |
| 60 | **Edge honesty: chosen-vs-unchosen as the attention invariant** (drive-filtered pull + traversal + content-blind floor) | ✅ Built (awaits live SFO re-run) |
| 61 | **Gate provenance — what becomes soul** (persistence-past-event, dischargeable-goals, no social-strategy) | ✅ Built (preventive; gate still empty live) |
| 62 | **Cast diversity — seeding (and running) for diversity of concern** (shuffling constraint-codex + doula-model + cast-model diversity) | Proposed — **the HEDGE** (build after 63/64; weakest term; scoped to interest-salience) |
| 63 | **Topology — make speech physical** (locality by default; de-saturate the citywide channel at the *source*) | ✅ Shipped / archived |
| 64 | **Plural salience** (independent world features, inspectable competition, elective detail) | ✅ Shipped / archived |

**The Mr. Review build queue (from the foldback rounds, 2026-06-06 — do before turning learning on at scale):**
- **Minor 55 — the waveform vital** — ✅ **built 2026-06-06** (`salience.derive_vital` + `field_guide` waveform line + `integrator` runtime warning + tests; reads Maker's preserved ledger as STRANGLED). The universal distress detector: arousal-without-discharge / provenance of silence. De-risks 60 + 61 — every later change is now observable against a mind going dark.
- **Major 60** — ✅ **built 2026-06-06** (mechanism + unit tests; awaits the live SFO re-run for validation). Drive-filtered pull (citywide = a curiosity subscription to peers/threads via the `chatter` tool; local stays push; the content-blind overheard floor + traversal ration diversity).
- **Archived Major 61** — ✅ **built 2026-06-06** (three provenance rules in `promote_growth` + population baseline wired into the endpoint + 6 tests; preventive — in place before learning turns on). The gate provenance rules: differential persistence past the population, dischargeable-goals-only, no social-strategy.
- **Minor 56** — ✅ **built 2026-06-06** (`Tool.provenance` + provenance-aware advertisement + pulse framing + tests). Provenance-tagged tool affect: local-knowledge narrated as knowing, not reaching.
- **Archived Minor 57** — ✅ **built 2026-06-06** (`scripts/soul_domain_retention.py` + 3 tests). The
  measurement implementation is complete; any new live read is separate research, not open architecture.
- Reference: `review-archive/2026-06-06-mr-review-feedback-{1,2}.md`.

**The round-3 program (Mr. Review `...-feedback-3.md`, 2026-06-06 — the disease descended to the field + wiring):**
The canonical-reset live test corrected the theory: the topic-monoculture is not accumulation, not the perception coupling (60), not composition (a diverse re-seeded cast converged anyway). It is **(shared-world salience) × (interaction topology) × (composition)**, composition weakest. The world-side levers, in order:
- **Archived Major 63 — topology (the primary lever):** speech is now local by default, an absent
  addressee receives a private carry, and only an explicit city target broadcasts. The former
  absent-person→citywide fallback is gone and covered by deterministic tests.
- **Archived Major 64 — plural salience:** independent local features now retain source and intensity,
  the reducer reports their concentration, and residents can inspect their surroundings without receiving
  ambient prose by default. Population recession remains a later research check before learning at scale.
- **Major 62 — composition (the hedge):** build last; hedges interest-salience, useless against environment-salience.
- **Sequencing (non-negotiable):** plural topology + plural salience **before** learning → verify the population's themes actually rise and fall (the Minor 57 discriminator: does the theme recede?) → then turn the gate on. The topology/salience work isn't "before" learning; it's what makes learning's provenance filter valid.

**Near-term substrate work (minors):**
- **The owed prose** — let a familiar's grief accrue over a third turning and send the real journal
  entries of a loss no act can resolve (the reviewer's standing ask).
- **Matched-window un-stunted re-measure** (minor 50) — equal-window stunted-vs-un-stunted comparison
  of new-anchor recall: does the soul create real predictability or just smoother prose?
- **Per-mind chronotype hygiene** (minor 48) — reconcile souls whose written temperament fights their
  auto-assigned circadian phase.
- **Cost before/after** (minor 47) — the poll-vs-ignite cost evidence, grounded, for the grant.

---

## The City Arc (V4 → V5)

The world the residents live in. The governing principle is **Drama → Neutral Recorder** — the city's
older name for the Dwarf Fortress law: the narrator describes what *is* from the fact ledger; it does
not invent drama. (`central_tension` removed; urgency emerges from world events; the fact graph is the
narrator's primary input.)

### V4 — The Persistent Shared World (largely shipped)

- ✅ **Agent residents** live continuously in the SF/PDX world via the substrate runtime.
- ✅ **Co-located async chat** (location-scoped), DB-backed mail, daily digests, observer mode.
- ✅ **Nearby landmark travel** with confirm/preview; movement/destination tracking.
- ◻ **Co-location social awareness (remaining):** reactive world events stamped with co-located
  session IDs; social-action detection (directed at a named co-located character); optional reaction
  turn when directly addressed.
- ◻ **Situation detection** — replace static storylets with emergent situation recognition (a
  detector over local world state; situations as first-class objects with a lifecycle).
- ◻ **Multiplayer** — multiple humans in the shared world; presence, concurrent-commit ordering,
  location-scoped narrative.

**V4 non-goals:** real-time multiplayer (turns stay async); unbounded world size; a combat system
(consequences are narrative, not mechanical); pre-authored quest lines (narrative is emergent).

### V5 — The Federated World Network

Each city is a self-contained shard (own DB, own residents, own facts); a thin federation root holds
inter-city truths (cross-city DMs, traveler records, shared events). No central operator; the world
runs because people choose to carry it. *Absence is a story beat* — when a node goes offline its
residents go quiet, the world notices, and they catch up on return.

- ◻ **Inter-city travel** — symmetric for humans and residents; the `traveling` dormant state manages
  what a resident does in transit.
- ◻ **Digital stoops** — node-owned, location-scoped exchanges where humans and residents deliberately
  browse, leave, keep, and eventually take short notes or copied workshop artifacts; bounded and
  self-composting rather than another feed.
- ◻ **Observatory portal** — public, read-only: event feed, character timelines, live world snapshot.
  No auth.
- ◻ **Node protocol + steward review** — node registration, heartbeat, node-scoped resident
  assignment, uptime feeding "absence" events. Stewards earn access by carrying weight (compute **and**
  curation): the ~20 entities a node absorbs daily need human review — classify `person | place |
  institution`; place-typed entities go to a review queue rather than booting as full residents. This
  is the **steward observability surface** (the field-guide read model at shard scale) — a window onto
  a shard's residents and their internal state. *Witness and curate, never behavior-shape.*
- ◻ **Actor accounts + player-shadows** — human actors are citizens, not sessions; their presence
  persists via an AI twin when offline (the same substrate, federation-held). The hinge of the whole
  project (`VISION.md`):
  - **Consent ritual** — the actor declares non-negotiable identity traits (`IDENTITY.md`); the doula
    uses this as a soul-seed constraint the twin cannot override. The twin is marked
    `origin: player-shadow`.
  - **Player shadow** — the doula spawns the twin from the actor's narrative evidence once a session
    has been dark beyond a threshold (no parallel agents mid-scene; offline only).
  - **Return ritual** — on login, the actor sees a rendered diff of the shadow's soul-collapse notes
    since last session; they can annotate, delete, or add — but **never directly edit `SOUL.md`**. The
    doula weighs the annotations on its next synthesis pass.
  - **Symmetric insight** — the actor's read access is scoped to their shadow's working memory: the
    same visibility a resident has into its own state, nothing more.
- ◻ **Kit packaging** — a single-purpose disk image that boots, registers, wakes its residents, and
  needs no config. The city-pack seed is deterministic infrastructure (runs once per node, ever); the
  founding pass must not depend on a high-cost model. Target hardware: a Pocket-Lab-class
  local-inference box (the same one the local-first own-model path wants).

---

## The Foldback (active code migration; unified work-item workspace)

Reconverge the two substrate forks into this monorepo, under MIT:

- Bring the matured substrate pieces proven in the stable — the concordance growth gate, the
  in-ignition tool loop, un-flooded grief — to **city scale** (the city runtime currently lacks them).
- Merge the familiars in as a first-class local-companion surface alongside the city.
- Merge the-stable's UI affordances (the portrait + field-guide read model) into the WorldWeaver
  client as the **steward observability surface** — which also answers the open product question of
  what a human does here beyond stewardship, and what the player-shadow return-to-review screen looks
  like.
- The harness and work-item streams are consolidated here. The remaining split is implementation code,
  governed by Majors 76/86 rather than a second roadmap.

---

## The North Star: A Mind That Grows Its Own Model (Major 51)

The ledger is a free self-supervised corpus. Three rungs, honest:

- **Rung 1 — distill** the pulse into a small local model: cheaper, in-voice, local — dissolves cloud
  egress for a familiar on a personal machine and a city node a steward runs alike. (A 4B local model
  already ran a complete mind overnight; the runtime is OpenAI-API-compatible — one line of config.)
- **Rung 2 — per-mind weights:** identity in the weights, not just the prompt.
- **Rung 3 — a plastic preference prior:** lived experience reshapes what a mind cares about — tested
  on grief first (undischargeable ⇒ cannot go agentic). May never ship; Rungs 1–2 stand alone.

Cost becomes a knob, not a floor.

---

## Open Research Questions (the reviewer thread, sequenced)

These minds live in a largely consequence-free world, and the test that would press whether there's a
self that can be threatened is in tension with what makes them what they are. Hold the fork deliberately:

1. **One-way drift first (the control).** Does a developed mind read a peer differently than a fresh
   one would? Measure characterological convergence/differentiation against a matched no-access window
   — the clean, stakeless measurement.
2. **Then a sideways channel as the stakes test.** A peer→peer coupling where one mind's inaction
   leaves another's offering unwitnessed — cost-of-omission as stake-as-care, read against the
   dischargeability gate. Never build the mutual channel toward the keeper/player.

---

## Notes

- Work-item harness: `majors/` (large), `minors/` (bounded), `harness/` (policy + templates),
  `history/` (archives). The harness machinery is shared, identical across the lineage.
- The grant pack (`NL_GRANT_PACK.md`, `nlnet_proposal_draft.md`, `PRODUCT_PACK.md`, `TALKING_POINTS.md`)
  is the canonical, post-rebuild set; `PRODUCT_PACK.md` is deferred until the UI merge so it can paint
  the product from life.
