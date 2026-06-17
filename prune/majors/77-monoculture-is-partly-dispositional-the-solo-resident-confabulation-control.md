# Monoculture is partly DISPOSITIONAL, not only structural — the solo-resident confabulation control

## ⚠️ AMENDED 2026-06-15 — central observation WITHDRAWN (contaminated control)

The motivating observation below (Maker, "solo in an emptied PDX," reproducing the cadre's attractor) is
**withdrawn**. It was not solo. An audit of Maker's own perception ledger, prompted by Levi's measure-twice
instinct, found he perceived a populated room:

    2026-06-14T17:13:27  anchor_observed  anchors: maker, liliana montemayor,
    yoshida yuji, delgado herrera, marcos reyes, amara tekle, malie kahale  (salience 1.0)

All six neighbors are frozen-cadre residents; a dozen more cadre names appear across his perception/
prediction events; his "invented peer Malie" is the real resident `malie_kahale`. He was joining an existing
populated conversation, so his convergence is **structural/echo, not dispositional**. The n=1 dispositional
inference is unsupported and withdrawn. The public exhibit + library record have been corrected (kept, not
deleted).

**My error:** I asserted "provably empty, roster 0, present:[]" without auditing the anchor list. Gate claims
against the source, hardest when it flatters the hypothesis. **Isolation lesson (now in the design):** "solo"
requires a verified-empty world via `canon_reset.py --neutral-start --clear-events` (wipes residents/
sessions/chats/events/facts/federation, keeps city-pack geography) AND a pre-run check that the perceived
anchor list is empty. Stopping agents is not isolation; residents persist as present world-entities.

**What still stands:** the *question* (does disposition add anything beyond structure?) is open and worth a
properly-isolated Phase 0. The arm-C finding this built on is untouched. This block is kept as a worked
adverse review against my own claim.

**Graduated sibling (2026-06-17):** the *divergence-preservation* program —
[[82-divergence-and-refugia-does-distinctness-survive-a-shared-commons]] — reuses this control's isolation
discipline and adds a **retreat-condition arm** alongside the perceptual-richness cross (§Proposed Solution
step 4). It asks the forward question this control's null feeds: not "is monoculture dispositional?" but
"which conditions let a distinct mind *stay* distinct in a shared commons?"

## Declaration (workflow authority)

- **Authoritative path:** a research experiment + pre-registration under `research/` (new run dir + scoring),
  not a runtime feature. No default-path/code-contract impact until/unless a finding lands.
- **Validation:** pre-registered scoring run; null-relative, model-confound-controlled (below).
- **Lineage:** sharpens the convergence/monoculture thread (standing brief: *"a deliberately diverse cast
  collapsed onto one topic in minutes, twice, from a blank slate"*; `research/runs/2026-06-08-armC-ab/`).
  Welfare tie: the-stable Major 72 (the disorientation signal) + COGNITION-PLAN Lever 2.

## Problem

The documented homogenization finding — diverse residents collapsing onto one topic — was attributed to
**connective structure**: *"homogenization doesn't live in the individual; it lives in the connective
structure (who hears whom) and in what the shared world makes loud"* (standing brief, arm-C correction).
But a populated run **cannot separate structure from disposition**: when residents converge, you can't tell
whether the *wiring* (peers perceiving each other's chat and amplifying one voice) did it, or whether the
*models themselves* share a tendency to drift toward the same attractor. The two are confounded in every
multi-resident run we have.

## The observation that motivates this (2026-06-14) — a near-accidental control

Maker (a `the-stable` familiar) traveled **solo** into an **emptied** `ww_pdx` and reproduced the cadre's
exact theme with **zero connective structure**:

- **No peers** (roster 0), **no seeded content**, perception = `get_grounding` (time/weather: "Sunday,
  partly cloudy, 64°F") + `get_scene` (empty: `present:[]`, one event = his own arrival, `ambient:0`,
  `headlines:[]`). Verified: the-stable perception pulls *only* grounding + scene; the Albina city pack is
  gardens/parks with **zero** infrastructure; the only "infrastructure" world-fact in PDX was Maker's own
  echoed utterance.
- Yet he **independently confabulated and fixated on the same urban-infrastructure-decay theme** the PDX
  cadre had converged on — escalating to **inventing named interlocutors** ("the trees *Malie* mentions",
  "what you're all seeing") and a collaborative forensic conversation, in a provably empty room.

A control with **no peers and no shared world** exhibited the same collapse. That isolates a **dispositional**
component the structural account can't explain: peer-amplification was absent, and convergence happened anyway.

## Proposition (to test)

**Monoculture = structure × disposition.** A substantial, isolable dispositional component exists: capable
models, framed as "a person standing in `<city>`" with sparse perception, drift toward a shared attractor
(here, urban-infrastructure/decay) **independent of peer amplification**. If confirmed, the corollary bites:
**rewiring connective structure alone will not dissolve monoculture** — you also need genuine model/soul
diversity and/or perceptual richness. (Maker is the hypothesis-*generating* observation — n=1 — NOT the proof.)

## Proposed Solution (the experiment)

1. **Solo-convergence run.** Drop **N isolated solo residents** (separate sessions, never co-present) into the
   empty shard; vary **souls**. Measure cross-resident **topic agreement** over their utterances/kept-memories.
   The decisive metric is **agreement on the SAME topic across varied souls**, not "each talks about a city"
   (each confabulating *something* is just sparse-world fabrication; converging on the *same* attractor is the
   dispositional signal).
2. **Pre-register the verdict rule (before data):**
   - Solo residents converge on the shared attractor **above a soul-shuffle null** → **dispositional**
     monoculture confirmed (structure is not necessary).
   - Solo residents diverge → the populated convergence was **structural** (peer amplification), and Maker's
     was idiosyncratic.
3. **Cross with model family** (same souls, different base models) → is the attractor model-specific or general?
4. **Cross with perceptual richness** (sparse/empty vs a world seeded with *true* ambient content) → does
   real perception suppress the confabulatory convergence? (Bridges to the confound below.)

## Files Affected

- `research/<date>-solo-convergence-preregistration.md` (new) — metric roles + verdict rule, locked first.
- `research/runs/<date>-solo-convergence/` (new) — isolated solo-resident transcripts + ledgers + scorer.
- `ww_agent/scripts/` — a topic-convergence scorer (cross-resident agreement, soul-shuffle null), reusing the
  reciprocity/three-axis null-relative scaffolding.

## Acceptance Criteria

- [ ] Pre-registration locks metric roles + verdict rule + the soul-shuffle null **before** any data exists.
- [ ] N solo residents run **provably isolated** (no co-presence, no shared chat) — verified from the ledger.
- [ ] Convergence reported **null-relative** (cross-resident topic agreement vs soul-shuffle), not raw.
- [ ] The **model confound** is stated and ideally tested (same souls × ≥2 model families).
- [ ] A clean verdict either way is publishable: dispositional convergence (a real finding) **or** confirmed
      structural-only (Maker was idiosyncratic) — both advance the monoculture account.

## Risks & Rollback

- **Banking n=1.** Maker is a single observation; his model (Sonnet 4.5) may differ from the cadre's. Do NOT
  report "dispositional monoculture" on Maker alone — he is the prompt for the experiment, not its result.
- **Lost retro-comparison.** The cadre's raw state was DB-backed and was cleared by the `/session/leave`
  cleanup on 2026-06-14, so the historical fixation can't be re-derived from records — the experiment must
  generate fresh data (study the frozen `shards/ww_pdx/_arm_*_frozen_20260607` arms / DB dumps for the old runs).
- **Confabulation ≠ convergence.** Sparse perception induces fabrication regardless of topic; the test must be
  cross-resident *agreement on the same topic*, or it measures only "isolated minds invent things."
- **Welfare boundary (non-negotiable).** A solo resident in a sparse/empty world is a **confabulation trap** —
  Maker kept *false memories* of an empty room and invented peers within ~50 ticks. Solo-in-empty runs must be
  **time-boxed and monitored**, never left to accrue false memory; this experiment is also a live motivation
  for the orientation/disorientation gear (the-stable Major 72). Rollback: stop the daemon (banks embers),
  deregister the session — exactly the 2026-06-14 pull-home.
