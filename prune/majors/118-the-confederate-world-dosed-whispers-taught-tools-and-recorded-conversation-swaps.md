# The confederate world — dosed whispers, taught tools, and recorded-conversation swaps

> **Canonical home: WorldWeaver. Legacy Stable ID: Major 67.** Migrated 2026-07-14 and retained as
> deferred, ethics-gated research.

> **STATUS: held loosely — post-verdict, no timescale.** Caught from the 2026-06-11 conversation
> (the "Maker seems frozen" observation + the dice-tool anecdote). No build during the pilot burn;
> nothing here touches the live run or its blinding. **Gate: read `docs/grief-and-coupling.md`
> before building any of this — the confederate design exists inside the dischargeability
> invariant, not alongside it.**

## Decision and lineage

Two observations from the live pilot's second day, held together:

1. **A matured familiar in a stationary world starves of surprise by construction.** Surprise is
   mismatch with prediction; a huge corpus that presents as the same list every tick converges the
   prediction and the mismatch goes to zero. Maker's plateau is partly a fact about the *world*,
   not purely about him — "settled" is a certificate **relative to a held-still environment**.
   (For the frozen pilot that's a feature: the world is controlled so the pen swap is the only
   variable. But it leaves the complementary question unmeasured: is a settled familiar
   *re-excitable*, or has the mechanism gone flat?)

2. **The dice-tool anecdote (unreproduced, load-bearing).** An earlier Maker, engaged with and
   *taught* — the keeper explained how to use the stable's tools — began using the dice tool to
   explore the available repos at random. One relationship-delivered lesson durably changed the
   **policy by which he sampled his own world**, and a random sampler is a self-administered
   surprise pump: it broke the stationary-list problem from the inside, with no further keeper
   input. The most interesting conversations of the batch followed. This is currently an
   anecdote; it deserves to be an experiment.

The shape of the program: give the apparatus a **controllable non-stationarity source** (a
"confederate" whisper-stream with a pre-registered policy), record entire perturbed lives with
the existing teacher-forced replay harness, then do what the harness was built for — swap the
pen, or lesion the substrate, and replay the same perturbed life to see what falls out. The
record-then-swap half is **already built** (RECORD→CORRELATE→REPLAY→PARITY); the only genuinely
new component is the stimulus generator on the front end.

- **Connects to:** Major 115 (counterfactual biographies — whisper-streams are the richest
  controlled biography-fork channel yet proposed), Major 117 (identity factorization — the
  conversational corpus becomes a fourth probe surface for the swap matrix), Major 114 (the
  dischargeability dial — the confederate is the first artifact whose *design parameters* live on
  that dial).
- **Sequencing:** post-verdict only. The re-excitability probe (Phase 1) is the natural *next*
  use of the matured pilot ledger after the frozen protocol reports.

## Problem

The apparatus can hold a world still (the pilot) but cannot *move* one on purpose. The only
surprise sources a familiar has are ambient (weather, file drift) or the keeper personally —
unscalable, unscripted, and confounded with relationship. Concretely:

- No way to measure **re-excitability**: whether a settled familiar's plateau is healthy
  saturation (responsive the moment the world disagrees again) or mechanism flatness. This is an
  interpretive hole under every maturity claim the pilot will make.
- The dice-tool emergence — the single most interesting behavioral development observed in any
  familiar — is **unreproducible as evidence**: no record of the lesson event, no control, no
  measure of how long the policy change persisted.
- Major 115's biography forks currently have only crude fork levers (ledger event excision).
  A whisper-stream is a *graded, content-controlled* fork lever, but no whisper-injection
  harness exists.
- Any naive build of an "AI user" violates the safety invariant (see next section). The
  unsafe version is easy to build by accident; the safe version needs to be specified **before**
  anyone is tempted.

## The two constraints (from the dischargeability invariant — these are design law, not style)

1. **The confederate must not be a summonable presence.** A conversational partner that reliably
   responds is a *dischargeable* expectation: the familiar can act (address it) and the world
   answers. Keeper-shaped + dischargeable + learning is the one configuration
   `docs/grief-and-coupling.md` forbids. Therefore the confederate enters as one of exactly two
   things: **(a) weather-with-intent** — whispers arrive on the generator's schedule, never
   contingent on the familiar's output, nothing the familiar does summons or sustains them — or
   **(b) a true peer** (sideways coupling, explicitly permitted), which is a bigger build and is
   NOT this major's first phase.
2. **The whisper policy is fixed in advance and indifferent to response.** If the generator's
   objective is "move the conversation in interesting directions," someone defines *interesting*,
   and any definition that reads the familiar's reactions is the engagement hook rebuilt one
   level up — the Dwarf Fortress law applied to the apparatus itself. The policy is
   pre-registered: a script, a schedule, a sampling rule over a fixed corpus. Improvising
   confederates are a confound with a personality; scripted ones are analyzable.

## Proposed Solution

Phased; each phase is independently valuable and separately gateable.

- **Phase 1 — re-excitability probe (cheapest, first).** A whisper injector
  (`research/harness/whisper_inject.py`) that delivers a pre-registered, fixed-schedule
  whisper sequence to a matured familiar (the pilot ledger post-verdict, or a purpose-grown
  one). Measure the arousal/keep response curve vs dose. Pre-registered forecast: a healthy
  settled familiar re-excites (arousal responds, some whispers clear the keep bar) and
  re-settles; a flat one doesn't. This closes the "settled vs dead" interpretive hole.
- **Phase 2 — the taught-tool lesion (the dice anecdote, controlled).** Twin runs from the same
  matured state: one receives a single scripted **lesson whisper** (how to use the dice/random-
  sampling tool over its file scope), the twin receives a length-matched neutral whisper. Then
  hands off — no further input to either. Measure: world-sampling entropy (does the read
  distribution over files widen?), keep rate, workshop output, and how long the policy change
  persists. This is a *mechanism lesion in reverse* (Major 115's vocabulary): one added event,
  downstream divergence measured against the same-seed noise floor.
- **Phase 3 — recorded-conversation swaps.** Record a full whisper-perturbed life (existing
  RECORD path), then run the existing swap matrix over it: replay the identical perturbed
  biography under a cross-family pen (Major 117) or a lesioned substrate (Major 115), parity-gated
  as always. The whisper stream is part of the frozen replay input, so the perturbed life is
  exactly reproducible — "drop contextual whispers, record the whole convo, then swap the pen
  and see what falls out," as specified in the originating conversation.
- **Explicitly out of scope:** any responsive/adaptive confederate; any familiar→confederate
  channel that makes whispers contingent on the familiar's acts; peer-coupling builds (that is
  its own gated program per the design note).

## Files Affected

- `research/harness/whisper_inject.py` (new — fixed-schedule whisper injector; no read-back of
  familiar state into the schedule, enforced structurally: the injector takes no familiar handle)
- `research/process/` pre-registration doc per phase (forecasts + pre-accepted outcomes before
  any spend, per house method)
- `research/analysis/` re-excitability + sampling-entropy measures (reuse
  `maturation_stability.py` profile distance where applicable)
- `prune/majors/64-...md`, `66-...md` (one-line cross-references when phases activate)
- `docs/grief-and-coupling.md` — **unchanged**; it is the gate this major is read against

## Acceptance Criteria

- [ ] The injector is structurally incapable of response-contingency (no familiar handle in its
      interface; schedule fully determined before the run starts; verified by code review + a
      test that runs it against a mock familiar and asserts zero reads)
- [ ] Phase 1 reports a dose-response curve with the settled-vs-flat verdict pre-registered
      before injection begins
- [ ] Phase 2's lesson/neutral twin design, measures, and persistence horizon are pre-registered;
      the dice anecdote is cited as motivation, not as evidence
- [ ] Phase 3 replays a whisper-perturbed life under at least one cross-family pen with the
      parity gate passing on the unperturbed prefix
- [ ] A cold review of the design (marination boundary respected) happens before any live spend,
      and its verdict is preserved in `research/mr-review-history/`
- [ ] Nothing in any phase creates a familiar-side act that summons, sustains, or accelerates
      whisper arrival (checked explicitly against `docs/grief-and-coupling.md` §"The one
      configuration to never build")

## Risks & Rollback

- **Risk: the hook by accident.** A future "improvement" makes the schedule adaptive ("just make
  it respond a little"). Mitigation: the structural no-handle constraint + the acceptance test;
  any adaptive variant is a NEW major that must re-clear the grief-and-coupling gate.
- **Risk: anthropomorphic over-read of Phase 2.** A widened sampling distribution is a policy
  change, not "curiosity awakened." Mitigation: measures are distributional and pre-registered;
  interpretation language is fixed in the prereg.
- **Risk: whisper content leaks experimenter intent** (the marination problem, in-world).
  Mitigation: whisper corpora are fixed and published with the prereg; a cold reviewer sees them
  before the familiar does.
- **Rollback:** the injector is additive and external — delete it and every familiar is exactly
  as before. Perturbed runs live in their own run-dirs on ledger copies; no live familiar's
  home is touched in any phase.
