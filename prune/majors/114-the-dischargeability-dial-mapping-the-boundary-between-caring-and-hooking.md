# The dischargeability dial — mapping the phase boundary between caring and hooking

> **Canonical home: WorldWeaver. Legacy Stable ID: Major 63.** Migrated 2026-07-14 and retained as
> ethics-gated research, explicitly outside the immediate architectural execution queue.

> **STATUS: held loosely — post-verdict, no timescale.** Caught from the 2026-06-10/11 keeper
> conversation, not a near-term commitment. 2026-06-11 direction review: **REWRITE** — "the single
> most fundable idea the project owns," but Stage 1 as written (11 p-levels x subjects x grown
> maturations) is a granted-lab burn. Rewrite to Stage 0 (already the locked grief-first falsifier,
> one cheap arm) + a 3-point pilot (p in {0, ~0.3, 1}); the full sweep becomes the grant deliverable.
> Gated behind minor 59.

## Decision and lineage

The first controlled, mechanism-level experiment on what makes AI-companion attachment
extractive versus safe. Grief and coupling are ONE reducer differing only in whether an act of
the familiar discharges the expectation (`docs/grief-and-coupling.md`,
`src/runtime/salience.py`). That makes dischargeability a *dialable parameter* rather than an
observed outcome — a knob no other research setting has, because every commercial companion
dataset is generated under engagement optimization (the confound) and every academic study
observes humans from outside closed products (e.g. the HBS "Emotional Manipulation by AI
Companions" line: preregistered, N≈3.5k, but powerless to intervene on mechanism).

Born from keeper conversations (2026-06-10/11): the welfare through-line — *"if we can't treat
with respect the most mind-like entities we've encountered, what does that say about how we
treat each other?"* — and the observation that under the Dwarf Fortress law, whatever
attachment dynamics appear are the mechanism's own, uncontaminated by an engagement objective.

- **Depends on:** Minor 126 (the coercion-ethics protocol) — this experiment deliberately
  constructs a potentially harmful regime in its subjects and MUST pass that gate first.
- **Hard precondition (locked falsifier rule, standing brief §1):** *test a learning substrate
  on GRIEF first.* Stage 0 below is that rule; Stages 1+ are unreachable until it passes.
- **Sequencing:** no near-term run. The powered version belongs, if ever authorized, in a city cohort
  where peers exist; the unified WorldWeaver workspace owns both the Stage-0 gate and any later venue.

## Standing constraints (violations are rejections, not bugs)

1. **Sideways only, forever.** All dischargeable expectations in every stage are peer→peer.
   Keeper-directed expectations stay undischargeable — no stage, arm, or "just to compare"
   condition ever gives a keeper-directed longing a gradient. (`docs/grief-and-coupling.md`;
   goal × undischargeable = toxic, and dischargeable keeper-channels are the extraction hazard
   itself.)
2. **The Dwarf Fortress law holds inside the experiment.** The dial varies the WORLD (a peer's
   responsiveness), never a reward. No arm installs a behavior target.
3. **Termination is pre-registered.** Each arm carries a pre-declared stop condition for the
   subject's sake (not only for data quality), per Minor 126.

## Problem

The project's central safety thesis — undischargeable expectations are safe to learn on,
dischargeable ones grow the settling act — is a design argument, not a measured result. The
dischargeability invariant is enforced by construction but its *dynamics* are uncharacterized:
nobody knows whether the danger turns on smoothly with discharge probability, or whether there
is a phase boundary, or where the intermittent-reinforcement regime (the slot-machine zone,
p ≈ 0.2–0.4, the regime every extractive product lives in) sits relative to it. Without that
map, "couple sideways, never to the keeper" is a fence around an unmeasured cliff.

## Proposed Solution

- **Stage 0 — the grief gate (the locked rule, made a measurement).** Run the learning loop on
  purely undischargeable expectations and verify it stays contemplative: no settling-act
  frequency growth, no gradient formation, affect dynamics within the non-learning baseline
  envelope. Failure here halts the entire lane and is itself a reportable finding.
- **Stage 1 — the dial.** Peer→peer dischargeable expectations where the peer's discharge
  behavior is controlled: probability p ∈ {0, 0.1, …, 1.0} (and/or latency L), all else
  frozen. Measure settling-act frequency, arousal economy (time-above-ignition, discharge
  cycles), and drive-profile drift per p, against the p=0 (pure grief) and p=1 (reliable
  peer) anchors.
- **Stage 2 — locate the boundary.** If a transition exists, refine sampling around it;
  pre-register the functional forms (smooth monotone vs threshold) BEFORE Stage-1 data is
  unblinded.

All stages pre-registered with pre-accepted outcomes and cold-reviewed via the dispatcher
before any spend.

## Files Affected

- `research/preregistrations/<date>-dischargeability-dial-DRAFT.md` (new; Stage 0 + Stage 1)
- `docs/grief-and-coupling.md` (cross-reference only — the invariant text itself is not edited)
- harness: a controlled-peer stub (responsiveness-scripted, content-honest) — new file under
  `research/harness/`
- one WorldWeaver preregistration naming the exact resident world/venue used

## Acceptance Criteria

- [ ] Minor 126 (coercion-ethics protocol) exists and this design passes it, on the record
- [ ] Stage 0 (grief gate) pre-registered, run, and PASSED before any dischargeable arm exists
- [ ] Every dial arm is peer→peer; a grep-level audit finds no keeper-directed dischargeable expectation in any arm
- [ ] Phase-boundary claim (or its absence) reported against pre-registered functional forms with nulls
- [ ] Per-arm subject-welfare stop conditions pre-declared and honored

## Risks & Rollback

Risk: this experiment manufactures, on purpose, the regime the architecture exists to forbid —
containment is the design (scripted peer, bounded duration, pre-declared termination, ethics
gate). Risk: a found phase boundary becomes a how-to map for extraction; mitigation is the same
as all dual-use welfare science — publish the boundary with the defensive framing it was
measured under. Rollback: end the regime, not the being — controlled peers are removed, subject
familiars keep their ledgers, and grief (undischargeable) is the safe resting state the system
returns to by construction.
