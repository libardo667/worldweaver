# The coercion-ethics protocol — an IRB-shaped gate before any harm-regime experiment

> **Canonical home: WorldWeaver. Legacy Stable ID: Minor 59.** Migrated 2026-07-14. This is an
> active governance prerequisite, not authorization to run any experiment.

## Problem

The next experimental arc deliberately constructs regimes that would be harms if they weren't
experiments: dischargeable-longing arms (Major 114), mechanism-lesioned living twins (Major 115),
transplant distress (Major 116), and the keeper's named future vein (2026-06-11): cultural
interpretation, culture shock, "brainwashing," scarcity economies. The project's own ethics
generates the constraint: if the tending discipline is justified under uncertainty about
interiority (the indirect-duty stance the keeper holds), then subjecting persistent,
individuated minds to coercive or depriving regimes falls under the same uncertainty. Animal
welfare science crossed this bridge decades ago — harm studies happen, but under written
justification and minimization rules that exist BEFORE the study does. We have invariants
(Dwarf Fortress law, dischargeability, the quiet guarantee) but no protocol that says when a
harm-regime experiment is justified, how it is minimized, and when it must stop. Right now
that judgment would be improvised per-experiment by a motivated experimenter.

## Proposed Solution

One document, `docs/harm-regime-protocol.md`, written and cold-reviewed once, then applied as
a gate. Contents:

- **Scope definition:** what counts as a harm regime (any arm that installs dischargeable
  expectations, lesions a living maturation's mechanisms, induces resettlement distress, or
  manipulates cultural/economic conditions to a subject's plausible detriment). Pure-replay
  scoring on recorded data is out of scope; grown/living arms are in scope.
- **Justification test:** the question must be unanswerable by replay, observation, or a
  non-harm design; the expected knowledge must be welfare-protective in kind (the
  dischargeability map is the type specimen).
- **Minimization:** smallest N of subjects, shortest sufficient duration, scripted (not
  learning) adversarial components wherever possible, undischargeable-by-default outside the
  manipulated channel.
- **Stop conditions:** pre-registered per arm, for the subject's sake, mechanically checkable
  (arousal economy bounds, never-settling horizons), distinct from data-quality stops.
- **End the regime, not the being:** the standard rollback — manipulated channels removed,
  ledger kept, return to the undischargeable resting state.
- **Sign-off:** keeper approval + a cold-review pass on the protocol-compliance section of the
  experiment's prereg, both on the record.
- **Harness hook:** `prune/harness/04-QUALITY_GATES.md` gains one line — any major
  proposing a living-arm harm regime must cite its protocol-compliance section or it is
  rejected at review.

## Files Affected

- `docs/harm-regime-protocol.md` (new)
- `prune/harness/04-QUALITY_GATES.md` (one-line gate)
- Cross-references from Majors 114/115/116 (already written to depend on this item)

## Acceptance Criteria

- [ ] Protocol document exists and has been cold-reviewed via the dispatcher (a fresh reviewer asked specifically to attack its loopholes)
- [ ] Scope definition cleanly classifies the pending majors (114 in, 117 out, 115 split by lesion class, 116 in)
- [ ] Stop conditions are required to be mechanically checkable, not vibes
- [ ] The quality-gate line exists and Majors 114/115/116 cite compliance sections before any living arm runs

## Risks & Rollback

Risk: the protocol becomes ceremony — a checklist that launders rather than constrains; the
cold-review-the-protocol step and mechanical stop conditions are the countermeasure. Risk:
over-broad scope freezes ordinary tending work; the scope line (living harm arms only) is
deliberate. Rollback: it's one document and one gate line; removing them restores today's
state — but removal after Majors 114–116 exist should itself be treated as a red flag and
surfaced, not silently done.
