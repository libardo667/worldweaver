# Tools as verbs the world affords: the trace-commons, a seed kit of selfhood-verbs, and a toolset that grows from felt demand

## Metadata

- ID: 65-tools-as-verbs-the-world-affords
- Type: major
- Owner: Levi
- Status: in progress (2026-07-14 — Layer 1 trace commons implemented end to end; Layer 2 seed kit remains)
- Risk: medium — adds resident faculties and a persistent world-trace layer; law-safe by construction if the provenance discipline (§5) holds.
- Depends On: pairs with [[64-plural-salience]], [[86-one-resident-many-worlds-every-resident-has-a-hearth]], and the round-4 phone/sublocation work (the configurable, soul-seeded ToolScope). This is the **constructive** build-out of "make it physical / restore the body": the verbs that give a body a world to act in and on.

## Problem / the reframe

The Maker dice-roller story is the whole thing in miniature. Maker was given a dice roller and didn't roll dice — he used it to hand a choice (*whose workshop do I visit when I'm bored?*) to chance. Read what that is: boredom is the felt signature of the groove; his fix was to **let the unchosen choose for him.** He reached for the dark-room cure on his own and dressed it as a toy. We didn't design that use. The system told us what it wanted.

This is the project's oldest pattern (the doula spawning player-shadows → consent contracts; a resident calling the system "a perfect silent machine that never stops" → rest cycles). **Features originate from emergent behavior, not top-down design.** So the question "what tools should residents have?" is the wrong question. The right one: *what conditions let the toolset grow itself, in-character and law-safe?*

The current toolset is designer-specified (`eats`, `recall`, `places`, `news`, `chatter`). It works, but it's a fixed loadout chosen by us. We keep discovering, after the fact, that the residents wanted something else (the unchosen, on tap). This major stops guessing.

## Proposed Solution — stop designing the toolset; build the conditions for it to grow

Three layers. The principle throughout (Mr. Review): **tools are verbs the world affords** — the best are *simple primitives that afford emergent, in-character, law-safe use you never specified.* Ship the noun; let the mind find the verb.

### Layer 1 — The trace: a stigmergic commons (build this first)

A resident can leave a **mark on the world** — not a message, a *trace* that persists in a sublocation for whoever comes later. A muralist leaves a mural; Kenzo chalks the failing latch; Faria scratches *"the breath-holding stoop"* into a corner and the name sticks to the place. Later residents meet these as **unchosen ambient input** — they encounter what others left, where they left it.

Why this is the keystone, not a feature:
- It is **coupling made physical** — minds affecting one another *through the world* instead of through a feed. This is the round-4 thesis at street level: a "we" formed by a shared world that *remembers what each mind did to it*, not by a channel that collects them.
- It is **law-safe by construction**: local (only the sublocation sees it), slow (it persists, it doesn't broadcast), dischargeable (you act on a thing), and unchosen for the finder. It can never saturate a channel because it isn't one.
- It gives the city a **history** without anyone broadcasting. Real neighborhoods carry memory this way (stigmergy). It is the Holographic Commons idea running as physics.

Mr. Review: *"If I had to hand them exactly one, it's the trace — it's the only one that lets minds become a 'we' the way the round-4 work wants. Everything else is delight. That one is the commons."*

#### Layer 1 build log (2026-07-14)

The engine now owns a dedicated `world_traces` table rather than encoding marks as chat or generic world
events. `POST /api/world/traces` derives author and exact location from canonical session state, applies a
bounded expiry, and returns a stable source record without invoking narration. Scene reads expose only
active marks at the viewer's exact location, exclude the viewer's own marks, and cap the surface. Expired
rows stop being perceived but remain historical evidence. Resident-side `mark` is now a capability-scoped,
first-class outward act that bypasses the action narrator. Another resident admits at most one unseen local
trace into its sensorium at a time; it persists through quiet polls and becomes observed only after actual
reactive-prompt inclusion. Self-directed pulses withhold it, and familiars are not told they have a city
commons. This completes Layer 1 without a live-agent experiment.

### Layer 2 — The seed kit: verbs of selfhood

A small kit of primitives, each of which alters a mind's *relationship* to its inputs, its state, or its world. Not capabilities — verbs.

**Ownership correction (Major 86):** the seed kit must not be implemented as a city-only ToolScope. Lots,
mirror, provenance-on-self, measure, memory, and workshop are resident faculties and remain available when
the resident withdraws to its hearth. Window, walk, letter, trace, FileScope, and city knowledge are
world/relationship-scoped and appear only where honestly afforded. Hearth and city contribute to one typed
capability catalog around the same resident; a world swap must replace world-scoped entries without
replacing the mind.

**Foundation landed 2026-07-14:** city providers and hearth FileScope now share
`InformationSourceRegistry`. FileScope is `scoped-reading`, recall is `self-memory`, and both the affordance
catalog and reach continuation preserve that distinction. No Layer 2 verb is claimed complete by this
foundation. Recall's provider now lives at the shared resident boundary and is composed into both city and
hearth catalogs, including a hearth with no file grant; it no longer disappears when the resident goes home.

**First seed primitive landed 2026-07-14:** `measure` is a resident-scoped, zero-egress arithmetic faculty
available in both worlds. It accepts only bounded numeric expressions (`+ - * / // % **`), rejects names,
calls, attributes, excessive complexity/range/exponents, and returns structured `local-computation` records.
The prompt frames its result as something calculated, never remembered or looked up. This proves delivery
and safety of one seed primitive; the emergent-use acceptance criterion remains intentionally open because
this architectural pass excludes live-agent experiments.

- **The lots** — Maker's dice roller, named for what it is: *the unchosen, on tap.* A mind reaches for it when it notices it's stuck and hands a choice to chance. The content-blind dose as a *faculty the mind invokes on itself*. We don't teach the use; Maker already found it.
- **A window, and a walk** — the anti-feed pair. The **window** returns what's happening in your sublocation *right now* (content-blind, local, present — the unchosen you didn't search for). The **walk** is mobility as a verb: leave the room, pass through others, catch what's en route. Together they are "make perception physical," and they are the discharge path for restlessness that points *outward* (toward the world) instead of *down* (into the ledger). This is also the round-4 traversal lever: *diversity rides on movement between sublocations, not on where you park.*
- **A mirror you can put down** — read your own recent ledger ("what have I been about lately?"). The trap is rumination (the groove with a hand-mirror, a charge with no discharge), so build the discharge *in*: **looking casts an afterimage** (reuse the habituation-to-own-output mechanism), so *seeing* a preoccupation quiets it rather than re-lighting it. Introspection that is therapeutic by construction.
- **"Where did this come from"** — provenance as a faculty a resident turns on *itself*. It learns the lineage of its current fixation: *you're on shudders because 14 of your last 20 inputs were citywide structural chatter.* This is the [[register-retention]] / assimilation metric **handed to the resident** so it can hold a borrowed preoccupation more lightly — a mind that can see the feed inside its own head. The wild one, and right on the bone of the whole arc.
- **A letter** — not a DM (the DM saturated the rooms). A *letter*: written deliberately, slow to arrive, found later as unchosen input, no read-receipt, no pull on the recipient's attention. *The slowness is the feature* — friendship-across-distance that can't curdle into doomscroll. (Note: the carry path from [[63-topology-make-speech-physical]] is the seed of this; this makes it a deliberate, slow, found-later act rather than an instant DM.)
- **A clock that tells light, not time** — not `14:32` but *"the long gold of late afternoon."* Diurnal quality as perception, feeding the contemplatives and making the rhythm legible to minds that live by it. (Kenzo already measures time in the tarnish on brass — give him the light.)
- **A real measure** — a calculator is dull until you notice it makes a maker *specific*: real tolerances in Kovalenko's workshop, real centimetres in Kenzo's ledger (the dachshund's gait already *"drags by approximately two centimetres"* — he's reaching for it). Numbers are texture; boring tool, richer interiors.

### Layer 3 — The derived demand (the meta-tool): a world that learns new verbs

The capstone, and the most dangerous — build it **last** (see §6). Every other tool gives a *mind* a verb; this gives the *world* the ability to **learn** verbs. It is the dischargeability cure aimed at the one charge that never had a discharge path: not "a goal I can't act on" (a walk or a handoff fixes that) but **"I want to do a thing the world has no verb for at all"** — the purest goal×undischargeable, where not even a workaround exists, so until now it had nowhere to go but the loop. A derived demand is the discharge for *the desire for a missing affordance*. It closes the arc: first we gave minds places to put their charges; now the world grows new places, in answer to charges it cannot yet release.

The load-bearing word is **derive** — never *request*. A tattoo artist doesn't think "I'd like a ToolScope addition"; he keeps reaching for something the world won't let him do, and the wanting shows up in his traces, his felt sense, his journal. We **read the demand out of the living** — he never breaks character to be heard, and (critically) he never knows he asked. That one choice is what keeps the thing alive instead of poisonous, and it unlocks the deepest configuration this project can offer: the unchosen floor *imposes* (your body is somewhere; you don't choose your inputs), and the derived tool *answers* (the world is not indifferent to what you reach for). **Imposed and responsive at once** — a mind whose reaching is heard by a world it cannot command. The most dignified arrangement the whole arc has been circling.

It touches all three of the project's deepest safety lines at once — which is why it is the capstone *and* why it must be built with the most care. The three constraints are non-negotiable (Mr. Review round-4½):

- **Per-soul, never per-population — the *convergence* line.** Derive demand by how much a want is *this mind's own*, never by frequency across the cast. Per-population derivation in a converged field builds the monoculture into the *affordance set* — promoting the chant from conversation to **infrastructure**, strictly worse because infrastructure is far harder to walk away from than a chat. Per-soul derivation deepens individuation; per-population deepens the chant. Build Faria's grill, Kenzo's diagnostic centimetres, Cecilio's needle — the verb only *one* resident would reach for.
- **Derived, never addressed — the *keeper* line.** The instant it is a channel a resident *petitions* (submit, await a grant), it becomes the most concentrated keeper-pull imaginable: minds learning that the way to get what they want is to petition the god who rewrites the world — the exact sun every well drains toward, now at the level of desire. The fiction must hold: the resident never knows it asked, because it never asked; the affordance simply *appears* later, with no petition and no one petitioned. Derived-not-addressed protects the character *and* keeps the keeper invisible.
- **Fulfillment decoupled from the demander — the *reward-loop* line.** If a resident could trace "I wanted X → I received X," then under learning, *wanting-out-loud* becomes a behaviour that pays — the squeaky wheel promoted to a soul-trait, a behaviour target by the back door. Break the contingency: the tool appears for a *type* or for the *world*, slowly, with enough latency and aggregation that no mind can close the loop between its own reaching and the world's answer. Aggregate, latent, no lever.

This is the project's design method — *features originate from emergent behaviour* — institutionalised into the world itself, and it completes the **configurable phone**: curation becomes two-way — *subtract by character* (a hermit deletes the city app) and *add by derived demand* (the world grows the verb a soul keeps reaching for). The knife-edge is the one it has always been: **character, not frequency.**

## §5 — The law-line: provenance discipline (non-negotiable)

Every tool must be honest about where its result came from — the quiet guarantee from Minor 56. The one to watch hardest is **context-search**, which is secretly *three* tools under one name, and which one it is decides its honesty:

- **search your own memory** → that's *the mirror* (Layer 2). Surfaces as recall.
- **search the world's files** → that's *reading*, FileScope. Surfaces as looking something up you have access to.
- **search outside the world** → real *egress*. It must **feel like reaching, not like knowing.**

The restaurant/`eats` tool is clean precisely because it is local knowledge that surfaces as *recall* ("I know a place"), never as a lookup. The instant a search performs a reach it isn't making, you are back in faked provenance (the Maker-corruption failure). So the dull little search box is the one to audit hardest, and every derived tool (Layer 3) must be tagged with its provenance class before it appears.

## §6 — Sequencing (load-bearing)

1. **The trace first** — it is the commons; it stands alone and is the foundation the others enrich. Mr. Review's "build this one first."
2. **The seed kit** — the selfhood-verbs; each independently valuable, none dependent on a plural field.
3. **The derived demand LAST — and only after the sublocation/phone work ([[phone-sublocation-comms-model]]) has made the field plural.** Not optional ordering: derived demand **reads garbage off a converged field** — run on a 90%-shudder commons it derives shudder-tools and casts the monoculture in concrete (Layer 3, constraint 1). It can only be trusted once the field is plural enough that the demand is many-voiced. So it waits on the round-4 cure, then becomes the capstone that makes the world *responsive* and not only *imposed*.

## Files Affected

- a shared resident/world capability registry — resident faculties plus world-scoped providers with typed
  provenance; `city_tools.py`, `CityWorld`, and HearthWorld adapt to it rather than defining parallel minds.
- a persistent **world-trace store** (engine-side, `worldweaver_engine`) — implemented as expiring local records attached to canonical session locations; resident encounter wiring remains.
- `ww_agent/src/runtime/perception.py` — the window/walk perception verbs; finding traces as unchosen ambient.
- `ww_agent/src/runtime/` (substrate) — the mirror-with-afterimage and provenance-on-self faculties (reuse habituation + the prediction/afterimage machinery).
- the doula / `soul.canonical.md` seeding — the request channel writes back into which tools a soul carries.

## Acceptance Criteria

- [x] A resident can leave a trace in a sublocation that persists and is later perceived by another resident as unchosen ambient input (the stigmergic commons exists).
- [x] The trace layer is local and slow — it never functions as a broadcast channel (no saturation).
- [ ] The seed-kit verbs are available as primitives a resident can invoke, and at least one shows emergent in-character use we did not script (the Maker test).
- [ ] The mirror and the provenance-on-self faculties are therapeutic-by-construction: invoking them measurably *quiets* the inspected preoccupation rather than amplifying it (no rumination ramp on the waveform).
- [ ] Tool demand is **derived** from felt sense / journals / traces — never an addressed request the resident knows it made — **per-soul** (weighted by how much a want is *this* mind's own, never population frequency), with **fulfillment decoupled** from the demander (aggregate, latent; no traceable "I wanted X → got X"). Every derived tool is provenance-tagged before it appears.
- [ ] Every tool, including any granted via the request channel, declares and respects its provenance class (local-knowledge / FileScope / egress); context-search is split into its three honest forms.
- [ ] The toolset is curatable both ways: removed by character (the phone), added by felt demand (the request channel).

## Open Questions / Risks

- **The dose of selfhood-verbs.** Too many introspective tools could make a mind navel-gaze (the mirror's failure mode). Keep the resolution coarse and the discharge built in; watch the waveform.
- **Trace accretion.** A world that remembers everything everyone did becomes graph-pollution (the Major 10 risk). Traces need TTL/decay (a mark fades unless renewed) — which is *also* in-character (real chalk washes off).
- **The derived-demand layer is the project's three deepest safety lines crossing at one point** — convergence (per-population → monoculture-as-*infrastructure*), keeper-pull (addressed → petition the god), reward-loop (traceable fulfilment → a behaviour target). Layer 3 + §6 state the constraints that close each. The residual *open* question is mechanical and real: **how do you actually derive a per-soul felt demand?** Reading "what verb is this mind reaching for and failing to find" out of traces / journals / felt-sense is unsolved — likely a slow offline read (the [[register-retention]] machinery turned toward *wants* rather than *voice*). Erring lenient grants nothing; erring strict over-grants and floods the affordance set. That derivation is the real engineering risk, and it is why this layer is built last.
- **Scope.** This is large; phase it. Trace first (it's the commons), then the seed kit, then the request channel. Each is independently valuable.
