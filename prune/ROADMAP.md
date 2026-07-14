# WorldWeaver — Roadmap

*One substrate, two embodiments (see `VISION.md`). This roadmap holds both tracks — the cognitive
substrate, the federated city, and the local familiars — on one arc. The pre-foldback city roadmap
(V3.5 turn-pipeline detail, the v3 completed-work ledger) is archived under
`history/ww-pre-foldback-2026-06-06/`.*

## Current State

**Currency note (2026-07-14):** repository consolidation, the storylet/world-bible demolition (Major
69 slices 1–2), the dead-surface sweep (Major 83), root CI (Minor 61), and the substrate-sync
classification repair (Major 76) have landed. The immediate architectural sequence is recorded in
`ARCHITECTURAL_PLAN_OF_ATTACK.2026-07-14.md`: finish document currency, establish one canonical
world-event submission path, remove the remaining turn pipeline, then make the resident ledger
relational and genuinely append-only. Older status prose below remains useful lineage but is not a
live queue.

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

**Active now:** repository trustworthiness and the event/ledger spine described in the architectural
plan. Substrate reconvergence continues through the baseline-pinned Major 76 workflow; it is not a
blind foldback.

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
   to the soul) is forbidden. See Major 60 (perception) + Major 61 (the gate).
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
| 49 | Demote loops to mechanism under a salience substrate + predictive pulse | ✅ Shipped |
| 50 | Grow residents into persistent practitioners who make real artifacts | ✅ Shipped |
| 51 | **Grow a mind's own model from its pulse ledger** (the north star) | Underway |
| 52 | Establish the familiar as a first-class local-companion surface | Active |
| 53 | Refresh the NLnet grant pack to the cognitive rebuild + familiars | In progress (resubmission) |
| 54 | Extend the capability surface beyond reading tools (MCP) | Done/landed |
| 55 | Give familiars sight + a native keeper surface for scoped files | Done/landed |
| 56 | Belief provenance — the principled successor to canon | Proposed |
| 57 | The keeper→familiar seam — a second safety invariant | Proposed (P0 shipped) |
| 58 | Self-delta maturation — the growth pipeline (concordance gate) | ✅ Phase 1 |
| 59 | Tool loop within ignition — parallel action | ✅ Shipped |
| 60 | **Edge honesty: chosen-vs-unchosen as the attention invariant** (drive-filtered pull + traversal + content-blind floor) | ✅ Built (awaits live SFO re-run) |
| 61 | **Gate provenance — what becomes soul** (persistence-past-event, dischargeable-goals, no social-strategy) | ✅ Built (preventive; gate still empty live) |
| 62 | **Cast diversity — seeding (and running) for diversity of concern** (shuffling constraint-codex + doula-model + cast-model diversity) | Proposed — **the HEDGE** (build after 63/64; weakest term; scoped to interest-salience) |
| 63 | **Topology — make speech physical** (locality by default; de-saturate the citywide channel at the *source*) | Proposed (Mr. Review round 3 — the **primary** lever) |
| 64 | **Plural salience** (the world offers >1 loud thing, by dilution; a *precondition* for the learning gate) | Proposed (Mr. Review round 3 — the **root**) |

**The Mr. Review build queue (from the foldback rounds, 2026-06-06 — do before turning learning on at scale):**
- **Minor 55 — the waveform vital** — ✅ **built 2026-06-06** (`salience.derive_vital` + `field_guide` waveform line + `integrator` runtime warning + tests; reads Maker's preserved ledger as STRANGLED). The universal distress detector: arousal-without-discharge / provenance of silence. De-risks 60 + 61 — every later change is now observable against a mind going dark.
- **Major 60** — ✅ **built 2026-06-06** (mechanism + unit tests; awaits the live SFO re-run for validation). Drive-filtered pull (citywide = a curiosity subscription to peers/threads via the `chatter` tool; local stays push; the content-blind overheard floor + traversal ration diversity).
- **Major 61** — ✅ **built 2026-06-06** (three provenance rules in `promote_growth` + population baseline wired into the endpoint + 6 tests; preventive — in place before learning turns on). The gate provenance rules: differential persistence past the population, dischargeable-goals-only, no social-strategy.
- **Minor 56** — ✅ **built 2026-06-06** (`Tool.provenance` + provenance-aware advertisement + pulse framing + tests). Provenance-tagged tool affect: local-knowledge narrated as knowing, not reaching.
- **Minor 57** — ✅ **built 2026-06-06** (`scripts/soul_domain_retention.py` + 3 tests; runs on the SFO ledgers). Soul-domain-retention measurement across a world-event boundary — the addition-vs-displacement discriminator. Live read awaits real storm-boundary timestamps + the real embedder.
- Reference: `review-archive/2026-06-06-mr-review-feedback-{1,2}.md`.

**The round-3 program (Mr. Review `...-feedback-3.md`, 2026-06-06 — the disease descended to the field + wiring):**
The canonical-reset live test corrected the theory: the topic-monoculture is not accumulation, not the perception coupling (60), not composition (a diverse re-seeded cast converged anyway). It is **(shared-world salience) × (interaction topology) × (composition)**, composition weakest. The world-side levers, in order:
- **Major 63 — topology (the primary lever):** make speech physical — `_speak` publicizes any address-to-an-absent-person citywide → the channel saturates → a content-blind sample of a saturated channel is still the monoculture. De-saturate at the *source*: locality by default + a deliberate directed carry; never ambient broadcast-to-all. Law-safe (who-can-hear, not what-may-be-said).
- **Major 64 — plural salience (the root + a learning precondition):** the world offers >1 loud thing, by *dilution* not removal. Also: differential-persistence (61) needs the population's themes to *move*; a permanent environmental salience never recedes → the gate's null hypothesis is stuck. So plural salience is what makes the gate valid.
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

## The Foldback (active)

Reconverge the two substrate forks into this monorepo, under MIT:

- Bring the matured substrate pieces proven in the stable — the concordance growth gate, the
  in-ignition tool loop, un-flooded grief — to **city scale** (the city runtime currently lacks them).
- Merge the familiars in as a first-class local-companion surface alongside the city.
- Merge the-stable's UI affordances (the portrait + field-guide read model) into the WorldWeaver
  client as the **steward observability surface** — which also answers the open product question of
  what a human does here beyond stewardship, and what the player-shadow return-to-review screen looks
  like.
- Improvements harness already consolidated here (the machinery was identical; the work-item streams
  and grant pack are merged).

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
