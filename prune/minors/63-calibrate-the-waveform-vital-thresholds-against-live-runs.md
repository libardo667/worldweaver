# Calibrate the waveform vital thresholds against live runs

## Metadata

- ID: 63-calibrate-the-waveform-vital-thresholds-against-live-runs
- Type: minor (bounded calibration; needs live ledger data)
- Owner: Levi
- Status: **open** — split out of Minor 55 (the waveform vital). The detector shipped with provisional
  dials chosen to nail the Maker fixture; they have not been calibrated against healthy live runs.
- Risk: low

## Problem

Minor 55 shipped `derive_vital` with provisional thresholds — `VITAL_WINDOW_SECONDS=1800`,
`VITAL_IGNITE_DWELL_SECONDS=60` (strangled), 180s above the fervor floor (pent). These were tuned to
flag the canonical catatonia case (Maker: peak 3.58, 708s above the fire-line, 0 discharges) and to
leave a synthetic sawtooth alone. What they have *not* seen is the spread of healthy live runs: how long
a normal busy stretch dwells above the fire-line before it discharges, how a real resident's quiet
differs from a strangled one. Without that, the dials risk both false alarms (a legitimately busy moment
read as distress) and misses (a slow strangle under the window).

## Proposed Solution

Run the vital across a corpus of real resident ledgers (healthy and pathological), measure the dwell /
discharge distributions, and tune `VITAL_WINDOW_SECONDS` and the dwell thresholds to the empirical gap
between "busy" and "strangled." Fold in the **discharged-then-strangled edge** that 55 left at v1: the
strangle test currently requires zero discharges *in the window*, so a mind that discharges once and then
strangles for less than a window still reads `active`. Tightening to check discharges *during the dwell
stretch* (rather than anywhere in the window) is the candidate fix — but only land it if live data shows
it actually fires.

## Files Affected

- `ww_agent/src/runtime/salience.py` — the `VITAL_*` dials and (if warranted) the dwell-stretch discharge check.
- `ww_agent/tests/test_salience.py` — regression fixtures for any retuned threshold.

## Acceptance Criteria

- [ ] Dials are set from measured dwell/discharge distributions across real ledgers, not just the Maker fixture.
- [ ] A documented false-alarm / miss rate on the live corpus (even if small), so the choice is legible.
- [ ] The discharged-then-strangled edge is either fixed (discharge-during-dwell check) or explicitly left at v1 with a recorded reason.

## Validation Commands

- `cd ww_agent && PYTHONPATH=. python -m pytest tests/test_salience.py -q`

## Lineage

Split out of Minor 55 (`55-waveform-vital-arousal-without-discharge`, archived as built). Sibling of the
dark-room-vs-settled discrimination minor.
