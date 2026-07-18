# Riley leaves the hearth under their own steam — 2026-07-17

## Purpose

Observe one resident for long enough to test the newly connected hearth-to-city edge, the corrected
action-tendency gate, normal city movement, and cleanup without telling the resident to leave home or
explore.

This was a runtime usability check, not a population or monoculture experiment. Private prompts, felt
sense, action prose, workshop writing, memories, and information contents were not reviewed. The report
uses only content-blind tick receipts and structural movement outcomes.

## Setup

- Resident: Riley Esposito
- Starting state: parked at Riley's hearth
- City: Portland (`ww_pdx`)
- Temporary pulse model: `anthropic/claude-sonnet-5`
- Duration: 30 minutes at the natural 20-second cadence
- Action tendency: enabled for this run only
- Temperature: model default
- No task, movement instruction, exploration instruction, or arousal manipulation

Command:

```bash
python dev.py resident \
  --city ww_pdx \
  --resident riley_esposito \
  --wake \
  --duration 30m \
  --model anthropic/claude-sonnet-5 \
  --action-tendency
```

## Structural result

| Measure | Result |
|---|---:|
| Wall time | 1,800.112 seconds |
| Natural ticks | 83 |
| Hearth ticks | 66 |
| City ticks | 17 |
| Inference calls / pulse attempts | 9 / 9 |
| Accepted and routed pulses | 8 |
| Successful actions | 8 |
| Successful `write` actions | 6 |
| Successful `move` actions | 2 |
| Private information reads | 0 |
| Settling pulses | 4 |
| Reactive ignitions | 2 |
| Venture pulses | 3 |
| Prompt / completion tokens | 36,868 / 9,004 |

Venture-gate receipts reported `opened` three times, `settling` four times,
`reactive_ignition` twice, and `fervor_not_due` on 74 quiet ticks.

## What happened

Riley remained at the hearth for the first 65 ticks. Four settling pulses produced ordinary private
`write` actions while the long stretches between them remained quiet. Enabling action tendency did not
turn every heartbeat into movement.

The first venture gate opened at tick 42. The model returned an invalid pulse with an `act` object whose
required body was empty. The runtime dropped the pulse and did not move Riley. This is a real interface
failure at the movement boundary; it is not evidence that the venture mechanism itself failed.

After the run, the movement contract was narrowed to the world input that actually matters: a `move` with
a non-empty destination target may omit redundant body prose. A move with no destination still fails, and
speech, writing, doing, and marking still require bodies. Riley's raw private pulse was not inspected, so
this report does not claim that normalization would certainly have recovered tick 42; it closes the exact
target-plus-empty-body shape without inventing text or intent.

The second venture gate opened at tick 66. Riley emitted a valid move to the reachable `city` edge. The
resident host completed the attachment transition, and tick 67 ran against Portland rather than the
hearth. The first city tick was an ordinary reactive ignition and completed a `write` action.

The third venture gate opened at tick 82 while Riley was in Portland. Riley completed a normal canonical
move from Alameda to Sullivan's Gulch. No ephemeral sublocation was created in Alameda or Sullivan's
Gulch. This proves that sublocation fallback did not replace or contaminate ordinary graph movement; it
was simply not chosen in this run.

At the duration boundary the runner retired the city session, returned Riley to the hearth, and released
the runtime lock. A read-only preflight afterward reported the resident ready and unlocked. No resident
process remained.

## What this supports

- A hearth resident can perceive and elect the city edge without an operator telling them to travel.
- A successful travel request changes the same resident's world attachment; it does not create a city copy.
- Action tendency remains narrow. Riley spent most of the run quiet and also retained writing as a valid
  outcome.
- The gate-reason receipt distinguishes “the model was never offered a venture” from “the gate opened but
  the returned pulse was invalid.” That distinction exposed a useful contract defect.
- Once in Portland, the same mechanism can produce ordinary graph-grounded city movement.
- Ephemeral sublocations coexist with canonical travel and do not appear unless a bounded local destination
  is actually chosen.

## What this does not support

- One resident leaving home once does not establish a healthy population rhythm.
- Riley did not speak to another resident, create a sublocation, travel between cities, or exercise a stoop.
- Six `write` receipts reveal only an action type. They do not establish what Riley wrote or whether it was
  varied, useful, or repetitive.
- This run does not answer whether several co-present residents converge on infrastructure-coded speech.
- This is not a controlled comparison between action tendency on and off. Riley's history changed between
  runs, and only one model was used here.

## Next architectural work

1. Run the versioned pulse contract through the synthetic multi-model battery before more live residents;
   target-only movement is now valid, while incomplete destination-free movement remains an error.
2. Use the new local, privacy-preserving conversation-health report over public city speech. It reports
   repetition, topic narrowing, pairwise convergence, and closed interaction loops without printing quotes,
   distinctive terms, private writing, memories, prompts, or hidden reasoning.
3. Use that instrument before releasing several residents together. Population observation should begin
   with public behavior and structural receipts, not manual reading of private ledgers.
4. Keep model training behind a stable interaction contract. If WorldWeaver later trains an affordance
   adapter or resident model, train it from validated successful trajectories and keep private identity
   material separate from shared tool-use training.
