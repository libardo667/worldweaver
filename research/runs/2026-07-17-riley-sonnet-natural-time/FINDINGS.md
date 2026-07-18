# Riley with Sonnet 5 at natural cadence — 2026-07-17

## Purpose

Check whether the new wall-clock runner exposes a meaningful resident rhythm, and observe a different
model family without instructing the resident to explore, move, speak, or perform a task.

## Setup

- Resident: Riley Esposito
- Temporary pulse model: `anthropic/claude-sonnet-5`
- Duration: 15 minutes
- Cognitive cadence: natural 20-second interval
- Temperature: omitted; model default
- Action tendency: off
- Starting state: previously parked at Riley's hearth
- Private prompt, felt-sense, action body, and workshop prose were not reviewed

Command:

```bash
python dev.py resident \
  --city ww_pdx \
  --resident riley_esposito \
  --wake \
  --duration 15m \
  --model anthropic/claude-sonnet-5
```

The runner used commit `d647ad2`. Its later content-blind attachment/action-kind receipt improvement is
commit `1bf9a83`; therefore this run can count actions but cannot recover their kinds from the receipt.

## Structural result

| Measure | Result |
|---|---:|
| Wall time | 900.019 seconds |
| Ticks | 41 |
| Inference calls / pulse attempts | 5 |
| Accepted and routed pulses | 4 |
| Successful actions | 4 |
| Private information reads completed | 0 |
| Surprise ignitions | 3 |
| Settling pulses | 1 |
| Fervor pulses | 1 |
| Venture pulses | 0 |
| Resting ticks | 0 |
| Prompt tokens | 21,970 |
| Completion tokens | 5,843 |

Riley remained at the hearth for the entire run. The structural ledger contains no attachment transition
during the 15-minute window. The runner parked cleanly afterward, released the runtime lock, and left no
agent process or Portland city session behind.

## Contract failure

One self-directed pulse was rejected because Sonnet put the source name in the verb field:
`reach.kind` was `recall`, while the contract requires a verb such as `inspect` and the separate source
`recall`. No action executed from that response and the resident did not enter a retry loop.

The pulse contract clarification landed afterward in commit `24b9277`. It now gives the explicit valid
shape `{"kind":"inspect", "source":"recall"}` and calls out the invalid source-as-kind form.

## What this supports

- Twelve compressed ticks were a poor behavioral test. Over real time, ticks were mostly quiet while
  occasional active moments completed normally.
- Sonnet 5 was not inert. Four of its five active attempts produced valid pulses and four successful
  actions, even with motor tendency disabled and no task prompt.
- It also did not act on every heartbeat: 36 of 41 ticks routed no pulse. Quiet and activity coexisted.
- The earlier synthetic result that every model initially chose a private reach is not a universal model
  behavior. In Riley's lived context, Sonnet's four accepted pulses acted without completing a private
  read. Situation and resident state matter.

## What this does not support

- The old receipt did not record action kinds. Successful hearth actions must not be relabeled as walking,
  city participation, or movement.
- This does not compare Sonnet fairly with Gemini: Riley had an existing history and the two runs used
  radically different elapsed time.
- It does not yet test how a fresh resident responds to a city, other residents, or travel affordances.

## Next test

Use the improved content-blind receipt with a fresh resident entering Portland at natural cadence. Keep
action tendency off. The receipt will distinguish attachment, pulse mode, reads, and action kinds so a
real city response can be compared without reading private prose.
