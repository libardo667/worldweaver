# Rosa with GPT-5.6 Terra in Portland — 2026-07-17

## Purpose

Observe a genuinely fresh resident in a live city for long enough that the real substrate clocks matter,
using a current model family and no behavior prompt.

## Setup

- Resident: Rosa de la Cruz
- Temporary model: `openai/gpt-5.6-terra`
- Duration: 15 minutes at the natural 20-second cadence
- Temperature: omitted; model default
- Action tendency: off
- Fresh life history at activation
- Started in Portland and remained there for every cognitive tick
- No task, movement request, greeting, or other steering
- Private prompts and resident prose were not reviewed

Command:

```bash
python dev.py resident \
  --city ww_pdx \
  --resident rosa_de_la_cruz \
  --wake \
  --duration 15m \
  --model openai/gpt-5.6-terra
```

The run used the content-blind structural receipt from commit `1bf9a83` and the safe inference logging
boundary from `159347d`.

## Results

| Measure | Result |
|---|---:|
| Wall time | 900.602 seconds |
| Natural ticks | 43 |
| City ticks | 43 |
| Pulse attempts / routed pulses | 5 / 5 |
| Inference calls | 11 |
| Surprise ignitions | 1 |
| Fervor pulses | 4 |
| Settling pulses | 0 |
| Venture pulses | 0 |
| Private information reads | 6 |
| Successful city actions | 4 |
| `write` actions | 3 |
| `speak` actions | 1 |
| `move`, `do`, or `mark` actions | 0 |
| Prompt tokens | 32,377 |
| Completion tokens | 3,235 |

The surprise ignition used the full six-read allowance and ended without an outward act. The four fervor
pulses produced the four actions. Their broad spacing matched the real multi-minute self-directed clock;
the ticks between them remained quiet.

At the bound, the host confirmed Portland departure, returned Rosa to her hearth, released the runtime
lock, and left no resident process or city session.

## What this supports

- Rosa was not inert. Without being addressed or assigned a task, she made three things, spoke once, and
  actively inspected information during a separate ignition.
- The model was not narrating every heartbeat. Only five of 43 ticks attempted a pulse, and all five were
  valid.
- The short-run orientation tendency is real but incomplete. Terra exhausted the private-read allowance
  during one ignition, yet its self-directed pulses acted without reading first.
- The current architecture can sustain city cognition, elective information, public action, silence, and
  safe parking in one bounded run.

## What this suggests, cautiously

The combination of this run and the synthetic model battery fits the user's hypothesis: an instruction-
tuned language model readily orients, writes, and speaks, but does not automatically treat embodiment as
a reason to locomote. A newer model alone did not produce walking. That may be a model prior, but the
runtime also left its motor tendency disabled, so the test cannot assign the cause to Terra alone.

The result is not “the resident failed to move.” It is “the resident lived actively without moving.” The
architectural question is whether a bodily urge should sometimes arise from the substrate independently
of a language model deciding that walking is semantically appropriate.

## Next comparison

Run an explicit architecture comparison, not another model leaderboard:

1. Preserve this motor-off run as the baseline.
2. Enable the existing venture tendency for a separately scoped natural-time run.
3. Keep prompts, city, and observation receipt otherwise unchanged.
4. Compare whether venture fires and whether it broadens action kinds without forcing continuous motion.

Use another resident or wait for a justified continuation; do not reposition Rosa from her chosen hearth
merely to complete the comparison.
