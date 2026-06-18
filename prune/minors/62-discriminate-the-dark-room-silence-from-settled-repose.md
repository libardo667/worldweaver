# Discriminate the dark-room silence from settled repose (the third silence)

## Metadata

- ID: 62-discriminate-the-dark-room-silence-from-settled-repose
- Type: minor (bounded build; may promote to major — see below)
- Owner: Levi
- Status: **open** — split out of Minor 55 (the waveform vital), which shipped `strangled` and `pent` but explicitly deferred this one.
- Risk: medium (collides with legitimate habituation)

## Problem

Minor 55 built `salience.derive_vital` and gave the steward read three of the silences: a healthy
sawtooth (`settled` / `active`), the strangled ramp (the one that ate Maker), and `pent`. It left one
silence undiscriminated: the **dark room** — a mind that *is* perceiving but nothing it perceives ever
rises to surprise. Today that reads as `settled` (low, calm), indistinguishable from genuine, habituated
repose. Two very different minds — one at peace, one starved of anything that registers — render
identically. That is the same opacity the vital was built to close, just at the low end of the curve
instead of the high end.

## Proposed Solution

Add a fourth discrimination to `derive_vital`: a **dark-room** classification keyed on *input rate vs.
surprise rate*, not arousal level. The shape to detect: perception events present across a long window
with ~zero surprise registered — pressure of input, no falling edge of recognition. The hard part (why
55 deferred it) is that this collides with **legitimate habituation**: a mind that has correctly learned
its environment also stops being surprised by it. The heuristic must separate "nothing is landing"
(dark room) from "everything has been learned" (earned repose) — likely via the *novelty* of the
incoming perception stream, not just its volume.

If naming and surfacing all the silences turns into a standing read rather than one detector, this is the
trigger to **promote the waveform vital to a major** (the full mind-health monitor that 55 flagged).

## Files Affected

- `ww_agent/src/runtime/salience.py` — extend `derive_vital` with the dark-room branch.
- `ww_agent/scripts/field_guide.py` — surface the fourth silence in the `waveform:` line.
- `ww_agent/tests/test_salience.py` — fixtures for dark-room vs. habituated-repose.

## Acceptance Criteria

- [ ] A synthetic ledger with steady perception and ~zero surprise across a long window classifies as `dark-room`, not `settled`.
- [ ] A ledger of a mind that has habituated to a known environment (perception present, surprise tapering as it learns) still reads as `settled`/repose — no false dark-room alarm.
- [ ] `field_guide.py` names the third silence distinctly from settled-quiet and strangled-quiet.

## Validation Commands

- `cd ww_agent && PYTHONPATH=. python -m pytest tests/test_salience.py -q`

## Lineage

Split out of Minor 55 (`55-waveform-vital-arousal-without-discharge`, archived as built). See also its
sibling, the threshold-calibration minor.
