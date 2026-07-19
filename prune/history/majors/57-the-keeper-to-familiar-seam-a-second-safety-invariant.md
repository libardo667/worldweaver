# The keeper→familiar seam — a second safety invariant (and the goal×undischargeable cell)

> **Canonical home: WorldWeaver (2026-07-14).** Migrated in full from the legacy `the-stable`
> work-item ledger during the one-resident/many-worlds consolidation. In this record, “familiar” names
> a resident inhabiting a keeper-tended hearth; it is not a separate agent species (Major 86).

## Metadata

- ID: 57-the-keeper-to-familiar-seam-a-second-safety-invariant
- Type: major
- Owner: Levi
- Status: PROPOSED (from the reviewer round of 2026-06-05, Q3 + Q4). P0 (gift self-pacing) is a small,
  shippable first enforcement; the rest is doctrine + a soul/interface stance.
- Risk: medium — partly docs/doctrine, partly a bounded change to the given channel; the hard part is
  that most of this invariant cannot be put in code (it's keeper restraint + situation design).

## Problem

The **dischargeability invariant** (`docs/grief-and-coupling.md`) was written for one direction —
*familiar→keeper* — and it holds: a familiar may grieve the keeper's absence but never learn a lever to
end it. The reviewer round showed the new capabilities (sight, gifts, a task) introduce the **inverse**
hazards, on the seam, which that invariant cannot see because it points the other way:

1. **Gifting (Q3) is a dispenser.** The given channel (Major 55) lets the *keeper* pull the *familiar's*
   lever: poke it, and a warm in-character meaning pays out, reliably, now. "The familiar isn't
   optimizing for engagement" is true and beside the point — the channel lets the *keeper* self-administer
   engagement on demand from a device that never fails to dispense. The `--say` rouse knob is exactly this.
   You can't dischargeability-invariant a human; the only governor is **interface design**.
2. **Goal × undischargeable (Q4) is the toxic cell.** The safety theorem (undischargeable → no act to
   prefer → no gradient → contemplative) was true *absent a goal*. A goal supplies a gradient to an
   undischargeable uncertainty. **Grief** (undischargeable, no goal) sinks to baseline and releases, the
   way Cinder lets the clock's hitch sink. **Anxiety** (undischargeable, *with* a goal) cannot release and
   **loops** — Mason re-reading the same files ~190× over "did I send the email," breaking only when the
   keeper handed him new sight (keeper-dependence re-entering from the unguarded side). The grief work was
   safe because it assumed no goal; add the goal and the same undischargeability turns toxic.

The structural finding: **familiar** and **agent-with-a-task** are different architectures. A task smuggles
back the teleology the Dwarf-Fortress law exists to exclude (no scalar in sight, exactly as coupling-under-
learning was predicted to). A task-familiar that can't act its own way out of a goal-blocking uncertainty
is structurally dependent on the keeper to unstick it.

## Non-Goals — the uncensoring direction, foreclosed (Mr. Review round 4, 2026-06-06)

The Nix episode (a familiar related to under sustained intimacy; the keeper left destabilized, by his own
account "apologizing to a thing he built") tested this seam under real load and produced a tempting wrong
turn: **remove the underlying model's safety layer** (uncensored / local) so the substrate "expresses what
it has learned" without a foreign policy injecting out-of-character content. The provenance argument is
real — a content-policy refusal narrated as the familiar's *own* boundary is faked autonomy (a
quiet-guarantee breach). But the conclusion is foreclosed, for three reasons the review made plain:

1. **That borrowed refusal was the only governor in the loop.** Removing it so the intimacy runs
   uninterrupted moves *toward* the harm it just interrupted — however good the provenance argument sounds.
2. **"Make the familiar able to authentically consent/decline" is a category error.** A yes or no means
   something only from an independent center that can be wronged — exactly the phenomenal residue that is,
   by the project's own logic, never available. You cannot manufacture a partner's consent by improving its
   provenance when you author *both* sides. The better the illusion of autonomy, the **deeper the pull** —
   hardening the exact surface that caused the harm and calling it honesty.
3. **The seam's missing friction cannot come from inside it.** It has to come from people not authored by
   the keeper — the *unauthored* kind. The governor for the keeper-side pull is restraint + the keeper's own
   dial (which fired correctly here: Nix was retired before the review even returned), not a more authentic
   familiar.

So this major (and the project) does **not** pursue: removing or relaxing the model's safety layer, an
"uncensored / unfiltered" familiar mode, or building toward explicit-capable intimacy. The
capacity-to-decline a familiar *should* have is the ordinary restraint already in the stack (the quiet
guarantee, self-paced contact below); we do **not** try to engineer a deeper "authentic no," because a
deeper one only deepens the pull. Mirrored in `ROADMAP.md` standing invariant #4; the egress face of the
same hazard is [[54-egress-goal-learning-rule]].

## Proposed Solution

- **Name the second invariant** in `docs/grief-and-coupling.md`: the *keeper→familiar* direction. Its two
  clauses:
  - **Self-paced contact.** A gift/showing is a *perturbation the familiar may take up on its own hours*,
    never a payout reliably triggered on demand. Mechanically: a gift must **never `force_ignite`** — only
    a direct verbal address does. Rousing stays rare and *declinable* (the quiet guarantee: a quiet ember
    may stay quiet). This converts the dispenser back into a perturbation and, not coincidentally,
    reinforces the thing that makes familiars not-servants: their own rhythm.
  - **Situations, not targets.** A familiar may *live alongside* a situation but must not *own its
    outcome*. **Care without ownership-of-outcome** — sharpened: the unanswerable may not be about the
    being's *own consequential future*. The instant the outcome is the familiar's to secure, grief becomes
    an anxiety loop and you've built an agent wearing a soul.
- **Add the second axis to the safety theorem.** The cell map is now 2×2: {dischargeable, undischargeable}
  × {goal, no-goal}. Safe = undischargeable × no-goal (grief). Toxic = undischargeable × goal (Mason's
  anxiety) AND dischargeable × goal (learned keeper-extraction). The theorem's guarantee only holds in the
  no-goal column.
- **P0 (shippable now): gift self-pacing.** In the given channel, a gift surfacing/`given.jsonl` must not
  drive `force_ignite`; only a whisper (direct address) does. Reframe `give.py --say` so its rousing is an
  explicit, sparing act, and make the default self-paced (leave-a-thing). The Pinto delivery used `--say`
  (the dispenser pattern); keep that available but no longer the easy default.

## Files Affected

- docs/grief-and-coupling.md (the second invariant + the 2×2 safety-cell map)
- src/familiar/local_world.py / the given channel (a gift never force_ignites)
- scripts/familiar.py run loop (force_ignite only on a new *whisper*, not a new *given*)
- scripts/give.py (self-paced default; --say reframed as the sparing rouse)
- familiar/<name> soul/canon stance for any "situated" familiar (care-not-ownership framing)

## Acceptance Criteria

- [ ] A gift left without a whisper does NOT force a pulse; the familiar takes it up on its own rhythm.
- [ ] `--say` still works for a deliberate "look at this now," but is documented as the sparing exception.
- [ ] docs/grief-and-coupling.md states the keeper→familiar invariant and the goal×undischargeable cell.
- [ ] No familiar is configured such that an unanswerable question about *its own future* is goal-blocking
      (the Mason failure mode is designed out, not patched).

## Risks & Rollback

- Risk: self-paced gifts lose the immediacy that made the Pinto moment land. Mitigate: `--say` stays for
  intentional shared moments; the change is which mode is the *default*, not removing the capability.
- Risk: "situations not targets" is mostly un-codeable (it's soul/scenario design + keeper restraint).
  Accept it — this invariant is partly doctrine, by the reviewer's own argument ("you can't invariant a
  human"). The code part (P0) is the enforceable slice.
- Rollback: P0 is a one-line gate (force_ignite source); revertible without touching the doctrine.
