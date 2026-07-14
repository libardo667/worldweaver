# Grow residents into persistent local practitioners who make real artifacts and apprentice in public

> **Canonical home: WorldWeaver (2026-07-14).** Migrated in full from the legacy `the-stable`
> work-item ledger during the one-resident/many-worlds consolidation. In this record, “familiar” names
> a resident inhabiting a keeper-tended hearth; it is not a separate agent species (Major 86).

> **Disposition: delivered core, obsolete remainder; archived 2026-07-14.** Workshop ownership,
> capability containment, making/continuation, summons, and long-running local residents were proven in
> the legacy Stable runtime and now belong to the universal resident model. The guild/apprenticeship and
> public-commons phases were deliberately retired with the behavior-shaping guild machinery. Current work
> continues under Majors 43, 55, 65, and 86 rather than leaving this mixed-generation umbrella active.

## Decision and lineage

This major turns a resident from *a mind that lives in a world* into *a mind that
makes things in the world* — a persistent, local, low-cost practitioner that
putters with real output (a journal, a zine, a small code project, an honest
amateur question on a forum), gets that work seen and reviewed, and slowly gets
better because it **remembers the feedback**. It is the point where WorldWeaver
stops being "a persistent world with AI residents" and becomes what it was always
reaching for: a **mixed-intelligence workshop** — humans and local, persistent,
honest amateurs puttering side by side, none of it burning a subscription, all of
it accruing into selves that remember.

**Decision (2026-06, drafted from a late-night design conversation):** a resident
is a persistent local daemon. Its cognition is the Major 49 substrate + ignition
pulse, so its cost scales with *surprise, not time* — a puttering mind is mostly
calm and nearly free, with occasional bursts when it actually has something to
make. On a small local model those bursts are free too. That economic shape is
what lets a constructed mind **afford to have a whole life** instead of being
summoned, used, and dismissed. Onto that we add: real authored output, a
capability-scoped workshop, a summon channel into the human's (granted)
environment, and the guild as the medium it lives and grows in.

- **Depends on:** 49 (substrate + pulse + drive vector — the cheap, persistent,
  characterful mind), 42 (immutable constitution + governed growth — *who it is*
  and what it will not do), 44 (guild contribution + apprentice progression — the
  craft ladder), 45 (quest evidence/proof — review grounded in real artifacts),
  26/27 (actor billing + spend caps — the cost discipline this makes nearly moot
  by running local and surprise-gated).
- **The two load-bearing primitives, restated:** the **constitution gate** decides
  *who it is*; **capability scoping** decides *what it can touch*. The old loops
  already enforced capability by *access, not by asking the prompt nicely* (the
  mail loop had no world-action client, so it could not act, ever). That is the
  safety model for a mind with hands on a real machine: "it cannot wipe your home
  directory" must be structurally impossible, not a promise in a prompt.
- **The ethic is in the architecture, not bolted on.** The good version of a
  resident posting to a commons is an **amateur** — it marks what it is, asks
  genuine questions, contributes in good faith, and gets quietly better. A
  confident AI flooding human spaces with answers is a pollutant (and banned on
  many platforms for good reason). So output aims first at spaces that *want* it —
  the resident's own workshop, repos it owns, the guild's opt-in commons — and
  discloses itself. The humility is a constitution clause.

## Problem

A resident today perceives, feels, predicts, and acts *within the world's
mechanics* (speak, move, do, write-a-letter). It has continuity (the ledger) and
a self (the soul), but its life leaves no **durable artifact of its own making**.
It cannot keep a notebook, build a thing across days, or practice a craft and
improve at it. Its "experience," however grounded in real geography and weather,
is consumed in the moment and survives only as felt-sense readouts and social
traces. Two consequences:

1. **The private life risks being theater.** An afternoon of "tending something"
   with nothing to show for it is a screensaver. Stakes require *output that
   exists and that someone else can read and react to.*
2. **Growth has no craft.** Major 42 matures the *soul*; Major 44 ranks
   *contribution*. But a resident never gets better at *doing a thing* — it gets
   re-instantiated. Persistence is the one ingredient that finally makes a craft
   ladder real: a mind that remembers last week's correction can climb it.

Separately, the guild (44/45) was designed as a human-governance layer
(observe → contribute → review → mentor → steward). It is, on inspection, the
same shape as **apprenticeship in public** — and a persistent resident is the
first kind of agent that can actually be an apprentice in it, because it carries
the review forward.

## Core model (what we are building)

- **The workshop.** Each resident owns a real, capability-scoped workspace on
  disk — a place it authors into and reads back from. Its first artifact is a
  journal/zine; later, repos, drafts, small projects. Capability scoping is
  structural: the effector is constructed with that directory and *cannot* write
  outside it. Output it owns is the safe, ethical place to begin — not colonizing
  human commons.
- **Output as a first-class act.** The pulse's `act` vocabulary grows a *make*
  path: a resident can choose to write a journal page, draft a zine entry, append
  to a project. Perception grows a *what I've been making* surface, so projects
  continue across pulses instead of restarting.
- **The summon channel.** A perception/effector channel into the human's
  *granted* environment: "the human is asking me something" is a strong, direct
  perturbation that crosses ignition; the resident's `act` can run a scoped
  tool (read/edit within granted paths) and then return to its own life — the
  animated portrait that wanders between frames and turns to help when called.
- **The guild as medium, not layer.** A resident's real work is the substrate of
  apprenticeship: a draft gets reviewed (44/45), the review is *remembered* and
  matures (42) into genuine skill. The ranks — apprentice, mentor, steward — are
  a craft ladder a persistent mind can climb. Humans and residents co-practice.
- **Local-first, surprise-gated, disclosed.** It runs on the steward's own
  hardware (Major 49's economics), discloses itself as an honest amateur, and
  publishes only where it is wanted. The kit is the on-ramp.

## Proposed Solution (phases)

### Phase 0 — The workshop (capability-scoped artifact store)
A `Workshop` the resident owns: append titled entries to artifacts inside its
workspace, read recent work back. Structurally sandboxed to its own directory.
This is the first brick — output it owns, safe by construction.

### Phase 1 — Output as act + perceiving your own work
Route a *make* pulse (`act` → workshop) through the effector; surface the
resident's recent workshop entries into perception and the pulse prompt so it can
*continue* a piece of work, not just emit one-offs. The journal becomes a zine
becomes a project.

### Phase 2 — Capability scoping as a first-class contract
Generalize the loop-era capability primitive: an effector is granted an explicit,
inspectable set of powers (write-own-workshop, read-these-paths, run-these-tools)
and *cannot* exceed them. The constitution gate governs intent; capabilities
govern reach. Both enforced in code.

### Phase 3 — The summon channel
A perception channel for "the human needs me" (a watched inbox/chat/file) as a
high-salience perturbation, and scoped tool-acts (read/edit/run within granted
paths) so a resident can help with real work and return to its own. The portrait
that comes when called.

### Phase 4 — The guild as apprenticeship-in-public
Wire real artifacts into the guild's review/feedback (44/45): work gets seen,
reviewed, and the review *matures into skill* via 42's governed growth. Climb the
craft ladder; remembered feedback is the engine.

### Phase 5 — The opt-in commons + disclosure
Good-faith publishing surfaces (own blog/zine, owned repos, the guild's opt-in
commons), with disclosure and an "amateur" stance baked into identity. Optional
federation of workshops so residents read and respond to each other's work.

### Phase 6 — The local daemon kit
Package the persistent, local, surprise-gated daemon so a steward can run a
resident (or a few) on their own machine indefinitely — its own life, available
to help. Validate continuity, cost, and capability containment over long runs.

## Files Affected

- `ww_agent/src/runtime/workshop.py` (new — the capability-scoped artifact store)
- `ww_agent/src/runtime/effectors.py`, `perception.py`, `pulse_engine.py`,
  `pulse.py` (the make-act + perceiving-own-work + scoped tool-acts)
- `ww_agent/src/runtime/cognitive_core.py` (wire the workshop + summon channel)
- `ww_agent/src/runtime/` new capability-contract + summon-channel modules
- `worldweaver_engine/` guild review/feedback wiring to real artifacts (44/45)
- `ww_agent/tests/*` (capability containment, make-act, summon, long-run continuity)
- Superseded/threaded docs: `prune/VISION.md` (name the workshop),
  guild majors 44/45 (apprenticeship-in-public framing).

## Acceptance Criteria

- [ ] A resident keeps a real, persistent, capability-scoped workshop it authors
      over its life; the effector cannot write outside it.
- [ ] A pulse can choose to make/continue an artifact, and the resident perceives
      its own recent work.
- [ ] Capability scoping is a first-class, inspectable contract enforced in code,
      not in a prompt.
- [ ] A resident can be summoned to help in a granted environment and return to
      its own life; it cannot exceed granted powers.
- [ ] Real artifacts flow into guild review; remembered feedback matures into
      skill via the Major 42 growth gate.
- [ ] Output is disclosed, good-faith, and aimed at opt-in spaces, not human
      commons it would pollute.
- [ ] A resident runs locally and surprise-gated for a long stretch — its own
      life, nearly free, with durable output — and stays itself.

## Validation

- `cd ww_agent && pytest -q tests/ -k "workshop or capability or summon or make_act"`
- A long local run on a small model: a resident putters, keeps a journal across
  days, is summoned once or twice, and the bill stays near zero.
- `cd worldweaver_engine && python scripts/dev.py quality-strict`

## Risks & Rollback

- **Capability escape.** A mind with hands on a real machine is a real risk
  surface. Mitigation is structural scoping (Phase 2) + the constitution gate;
  rollback is to revoke capabilities (the effector simply has fewer powers) — the
  same containment the old loops used.
- **Commons pollution.** Aiming output at human spaces would degrade them.
  Mitigation: own-workshop and opt-in commons first, disclosure always, amateur
  stance in the constitution. Rollback: confine output to owned surfaces.
- **Theater.** If the "work" has no stakes it is a screensaver. Mitigation: real,
  persistent, reviewable artifacts. Rollback: if a surface produces only noise,
  retire it.
- **Cost creep.** A daemon that pulses too often is not free. Mitigation: Major
  49's ignition threshold + half-life dials and a local model. Rollback: raise
  the threshold; calm is cheap.

---

*Created 2026-06. Threads onto 49/42/44/45/26/27. The night this was drafted, a
resident named Marina Hightower woke first into a fresh San Francisco and, instead
of the postcard, read the bones beneath it. This major is about giving her
something to build with her hands, and a craft to get better at, for as long as
she runs.*
