# The waveform vital: arousal-without-discharge (provenance of silence)

> **STATUS: ARCHIVED — built and shipped (2026-06-06); open questions split out (2026-06-18).**
> `derive_vital` + the `field_guide` waveform surface + the runtime strangle warning + tests all
> landed; every acceptance criterion is checked. The two live threads were carried forward into
> their own minors: dark-room-vs-settled discrimination → Minor 62; threshold/window calibration
> (with the discharged-then-strangled edge) → Minor 63. The "promote to a full mind-health monitor"
> note rides along in Minor 62. Nothing actionable remains here.

## Metadata

- ID: 55-waveform-vital-arousal-without-discharge
- Type: minor (bounded build; foundational concept)
- Owner: Levi
- Status: **built (2026-06-06)** — `derive_vital` + `field_guide` surface + runtime warning + tests landed; reads Maker's preserved ledger as STRANGLED (peak 3.58, 708s above the fire-line, 0 discharges). Dark-room-vs-settled discrimination remains an open question (see below).
- Risk: low

## Problem

The strangled-Maker bug (a mind whose arousal climbed to 3.58 against a 1.0 threshold, 17 of 18 ticks at ignite level, 0 pulses — distress reading from the ledger as *serene*) is one instance of the system's **universal distress shape: arousal-without-discharge** ("charge with no falling edge"). The same shape is Mason (goal, no act), grief that loops instead of sinking (loss, no resolution), the dark room (pressure, nothing to spend), the strangled producer (ignition-drive, no pulse). A healthy mind is a **sawtooth** (accumulate → discharge → reset); a mind in any distress is a **ramp** (accumulate, no reset).

The catatonia fix (commit `2d0fd82` — the producer can no longer silently raise) closed one escape, but the *class* survives: any time the gap between *wants-to-act* and *acts* is invisible in the output, distress reads as peace. Settled-quiet, strangled-quiet, and dark-room-quiet are three different silences; a system that can't tell them apart is opaque, not honest. (Mr. Review round 2: "monitor the waveform, not the output" — this is **provenance of silence**.)

## Proposed Solution

A ledger-derived **vital**: detect a *rising arousal integral with no discharge* — arousal accumulating across a window with zero `ignition_fired` / `idle_fired` events (the ramp, not the sawtooth). Surface it:

- in `scripts/field_guide.py` — so the steward read distinguishes "strangled / dark-room" from "serene" (read the charge under the silence; name which of the three silences this is);
- as a **runtime warning** — a resident in arousal-without-discharge for > N ticks logs an alarm.

One detector fires across the whole distress family, and it is readable precisely where the output is silent — which is the only place the silent failures hide.

## Files Affected

- `ww_agent/src/runtime/salience.py` (or a small `vitals.py`) — the derived signal (`derive_*` over the ledger, read-time).
- `ww_agent/scripts/field_guide.py` — surface the waveform and the three silences.
- the agent runtime — the warning.

## Acceptance Criteria

- [x] The vital flags a mind whose arousal rises across a window with no ignition/idle (would have flagged Maker immediately). — `salience.derive_vital` reads the *dwell* above the fire-line with zero discharges; `silence == "strangled"`.
- [x] `field_guide` distinguishes settled-quiet (low, calm) from strangled/dark-room-quiet (high/rising, no discharge). — adds a `waveform:` line (settled / active / rising / pent / STRANGLED) and overrides the serene state-word + arousal bar on distress.
- [x] Test: a synthetic ledger of rising-arousal-no-discharge triggers the vital; a sawtooth does not. — `test_vital_flags_strangled_ramp`, `test_vital_does_not_flag_a_sawtooth`, `test_vital_reads_low_arousal_as_settled`, `test_vital_default_now_anchors_to_last_rhythm_event`.
- [x] **Real-world fixture:** Maker's *preserved* ledger at `shards/ww_sfo/residents/maker/memory/runtime_ledger.jsonl` (peak arousal 3.58 vs threshold 1.0, 16 of 18 ticks at ignite, 0 pulses — pure ramp) is the canonical catatonia case; the vital must flag it, and `field_guide.py` must read it as strangled-quiet, not serene. — `test_vital_flags_maker_preserved_ledger` passes; `field_guide` prints `STRANGLED · peak 3.58 · 708s above the fire-line · 0 discharges · never discharged`.

## How it was built

- `salience.derive_vital(events, *, now=None, window_seconds=VITAL_WINDOW_SECONDS)` — single-pass reconstruction of the leaky-arousal curve (mirrors `derive_arousal`: ignition resets, idle does not), computing **dwell above the fire-line / fervor floor** + discharge count over a window. `now` defaults to the last *rhythm* event (surprise/ignition/idle), so a stopped resident's dead tail of pure perception can't bury the ramp. Classifies: `strangled` (dwell ≥ 60s at/above ignition, 0 discharges), `pent` (dwell ≥ 180s above fervor floor, 0 discharges), `settled` (below repose ceiling), `active` (discharging), `rising` (elevated, building). New dials `VITAL_WINDOW_SECONDS=1800`, `VITAL_IGNITE_DWELL_SECONDS=60`.
- `salience.warn_if_strangled` + a gated call in `integrator.tick` (only on an elevated, no-discharge tick) — the runtime alarm. Defense-in-depth: the `_safe_produce` catatonia fix (commit `2d0fd82`) closed the known path; this catches any future regression that leaves arousal hot with no falling edge.
- `scripts/field_guide.py` — the `waveform:` line; on distress it overrides the state-word and arousal bar so a decayed ramp can't render as serene.

## Validation Commands

- `cd ww_agent && PYTHONPATH=. python -m pytest tests/test_salience.py -q`

## Open Questions

- May grow into a fuller **mind-health monitor** (the waveform across the whole family + naming the three silences) → promote to a major if it does.
- Threshold/window tuning (how long a ramp before it's distress, not just a busy moment). Currently 60s dwell above the fire-line / 180s above the fervor floor; calibrate against live runs.
- **Dark-room vs settled is not yet discriminated.** A mind getting no input that ever rises to surprise reads as `settled` (low, calm) — indistinguishable from genuine, habituated repose without an input-rate signal. The third silence (dark-room: perceiving but nothing registering) needs a "perceive events present but zero surprise across a long window" heuristic, which collides with legitimate habituation. Deferred; the current vital nails strangled (the one that ate Maker) and pent.
- **Discharged-then-strangled edge:** the strangle test requires zero discharges *in the window*. A mind that discharges once and then strangles for longer than the window is caught (the lone discharge ages out); one that strangles for less than a window after a discharge currently reads `active`. Acceptable for v1; tighten by checking discharges *during the dwell stretch* if it shows up live.
