# Make social feedback scoring continuous and add dampening evidence

> **STATUS: ARCHIVED — superseded by the salience substrate (Major 49); off-vision (2026-06-18).**
> Doubly stale. (1) Code path is gone: this item rewrites `ww_agent/src/loops/slow.py`, which no
> longer exists — the fast/slow/mail/ground/wander loop bank was demoted to pure sensorimotor
> mechanism beneath the `CognitiveCore`. "This keeps the current architecture" is no longer true.
> (2) Frame is off-vision: it treats a resident as something tuned by a persisted "social feedback /
> adaptation signal" — the pre-substrate, pre-welfare engagement angle. Under the current ethos,
> per-resident differentiation is carried by the soul's drive vector (`drive.py`) and affect derived
> over the append-only ledger ("the self lives in the soul + ledger + kept memory, not the model";
> VISION "A Mind That Grows Its Own Model"). The valid kernel — residents in one room responding as
> distinct people — is already met by the substrate, not by a scored feedback loop. No reframe;
> archived as a closed direction.

## Problem

[`ww_agent/src/loops/slow.py`](ww_agent/src/loops/slow.py)
currently records inferred social feedback with a small set of fixed positive
constants.

That creates two problems:

- the signal is too templated to differentiate residents strongly
- the system mostly rewards activity presence, with little negative or
  dampening evidence

In practice this means a resident with active social threads and movement/mail
intents can accumulate feedback that looks informative but is actually too flat
to support meaningful adaptation.

## Proposed Solution

Change inferred social feedback from fixed step values to continuous heuristics
derived from the actual runtime situation.

The scoring pass should:

- scale scores based on intensity, recurrence, urgency, and follow-through
- add negative or dampening evidence for overload, avoidance, stalled repair,
  social withdrawal under pressure, or repetitive low-value looping
- continue to clamp values into safe bounded ranges before persistence

This keeps the current architecture but produces a sharper adaptation signal.

## Files Affected

- `ww_agent/src/loops/slow.py`
- `worldweaver_engine/src/services/guild_service.py`
- `worldweaver_engine/src/models/__init__.py`

## Acceptance Criteria

- [ ] Inferred feedback scores are no longer limited to a handful of fixed constants
- [ ] Feedback can express both positive and negative or dampening evidence within bounded ranges
- [ ] Different residents with different behavior patterns produce meaningfully different dimension summaries over the same window
- [ ] Runtime adaptation remains bounded and stable after the scoring change
