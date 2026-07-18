# Action-tendency live check — 2026-07-17

## Purpose

Determine what `WW_ACTION_TENDENCY` actually changes, expose it as a safe one-run option, and observe whether
it broadens bodily action without adding a wander loop or forcing movement.

Private prompts, information results, resident prose, and workshop contents were not reviewed. All live
observations below came from content-blind receipts and structural action outcome events.

## What the switch does

The switch does nothing on ordinary quiet ticks, reactive surprise ignitions, settling pulses, or deep rest.
It is consulted only when the existing CognitiveCore rhythm is about to produce a fervor pulse. Fervor itself
requires moderate arousal to remain above `0.45` for about 180 seconds without crossing the ordinary ignition
threshold.

At that one decision point, fervor becomes venture only when:

- circadian wakefulness is at least `0.4`;
- perception exposes a reachable place or someone present;
- no successful `move` or physical `do` has warmed the world in the last five minutes; and
- the combined arousal/world-coldness strength clears the soft threshold.

A soft venture foregrounds `move`/`do` but leaves verbal action available. A hard venture withdraws the
workshop invitation and asks for `move` or `do`. The producer ranks an exact reachable target using the
resident's drive vector when available. This is part of the same pulse mechanism, not another scheduler.

The root operator command now accepts `--action-tendency`. It applies only to that resident run and does not
edit shard configuration or identity tuning. The older `WW_ACTION_TENDENCY` environment fallback remains.

## Run A: Jarosław Nowak, Portland

Command:

```bash
python dev.py resident \
  --city ww_pdx \
  --resident jarosaw_nowak \
  --wake \
  --duration 15m \
  --model openai/gpt-5.6-terra \
  --action-tendency
```

Jarosław was a newly seeded resident with an arts livelihood and a bare home location in Arbor Lodge. The
creator received no city-history context.

| Measure | Result |
|---|---:|
| Wall time | 900.464 seconds |
| Natural city ticks | 43 |
| Pulse attempts / routed pulses | 4 / 4 |
| Surprise ignitions | 1 |
| Fervor pulses | 3 |
| Venture pulses | 0 |
| Private information reads | 1 |
| Successful actions | 3 |
| Successful `write` actions | 3 |
| Failed `move` attempts | 1 |
| Inference calls | 5 |
| Prompt / completion tokens | 16,777 / 2,326 |

The first reactive pulse attempted to move from `Arbor Lodge` to `the duplex near Arbor Lodge Park`. The
flat city route graph rejected that plausible within-neighborhood destination with HTTP 404. The following
three fervor pulses wrote instead of becoming ventures.

The run exposed a motor-gate bug: world-coldness looked for `move`/`do` strings among the last twenty emitted
actions. The failed move therefore suppressed venture indefinitely in a sparse action history even though the
resident had not gone anywhere. Successful action outcomes now define world warmth, and that warmth expires
after five minutes. Focused tests cover successful, failed, and expired bodily action cases; the full agent
suite passes with the correction.

The failed destination is also direct live evidence for
[`prune/minors/32-ephemeral-sublocations-under-canonical-nodes.md`](../../../prune/minors/32-ephemeral-sublocations-under-canonical-nodes.md):
the map needs sublocations beneath canonical nodes rather than treating every home-, room-, booth-, or
stoop-scale destination as an invalid neighborhood route.

## Run B: Jarosław at his hearth

A five-minute follow-up restored Jarosław's last attachment, correctly returning him to his private hearth
rather than forcing him into Portland.

| Measure | Result |
|---|---:|
| Natural hearth ticks | 15 |
| Settling pulses | 1 |
| Venture / fervor / ignition pulses | 0 / 0 / 0 |
| Outward actions | 0 |
| Inference calls | 1 |

This supports the non-coercion boundary: enabling action tendency does not make a calm resident wander. It
also exposed a separate perception seam. The hearth briefing truthfully says the resident can move to `city`,
but the hearth scene's reachable graph is empty, so venture target selection cannot currently rank that travel
edge.

## Run C: María Ramírez, Portland after the fix

María was another newly seeded resident, living around Ardenwald, with no city-history creation context.

```bash
python dev.py resident \
  --city ww_pdx \
  --resident maria_ramirez \
  --wake \
  --duration 5m \
  --model openai/gpt-5.6-terra \
  --action-tendency
```

| Measure | Result |
|---|---:|
| Wall time | 300.513 seconds |
| Natural city ticks | 13 |
| Surprise ignitions / routed pulses | 2 / 2 |
| Venture / fervor / settling pulses | 0 / 0 / 0 |
| Private information reads | 12 |
| Outward actions | 0 |
| Inference calls | 14 |
| Prompt / completion tokens | 36,985 / 3,180 |

Both ordinary reactive ignitions occurred before the 180-second self-directed clock could mature; each
used six private reads and ended without an outward action. The action tendency correctly did not override
reactive perception or manufacture an extra pulse.

## Conclusions and limits

- The flag is a narrow modifier of an already-due fervor pulse, not a general movement or wake-up flag.
- It can be enabled for one bounded run without changing other residents or permanent shard behavior.
- Live operation remained quiet by default and parked both residents safely.
- The first run found and led to a fix for a real emitted-intent-versus-executed-action bug.
- Jarosław's attempted duplex move gives concrete support for the existing sublocation work item.
- No real model received a venture prompt after the gate fix in these samples. Synthetic mechanism tests prove
  the branch and prompt contract, but live behavioral effectiveness remains unproven.
- A future live check should not manipulate arousal merely to force a venture. It should add content-blind
  venture-gate reasons to receipts, make real hearth-to-city reachability visible, then observe a naturally
  keyed-up resident for long enough to see whether the corrected branch arises.
