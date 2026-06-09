# Pre-test package — reciprocity re-read of three frozen cohorts, before the venture-OFF run

*De-narrated on purpose (same rule as your desk). Below are the instrument, the raw numbers, the
cohort configs with their confounds laid bare, and what we are about to run. The interpretations we
reached are withheld — re-derive them, or break them. Three asks for you at the bottom.*

---

## The instrument (shipped: `reciprocity.py`; re-runnable on the attached ledgers)

It reads `pulse_act_emitted` events across a whole cohort's `residents/*/memory/runtime_ledger.jsonl`
and separates two things the project previously bundled under one name:

- **OUTWARDNESS** = person-addressed speaks / total speaks. (A speak's `target` is either a person's
  display name or the literal `"city"`. This is what the old `three_axis` CONTACT axis computed.)
- **TURN-TAKING** = of A→B person-addressed utterances, the fraction where B emits a B→A
  person-addressed utterance **within a time window**. Reported as a *band* over windows
  {5, 15, 30, 60 min, unbounded}, because the number is window-sensitive.
- **Concentration** = how many distinct dyads carry the answered utterances, and the top dyad's share.
  (Reported because one ping-ponging couple can masquerade as population-wide engagement.)

`target` values are display names (e.g. `"Nalin Sharma"`) or `"city"`; the reader maps each
resident dir → display name via `identity/IDENTITY.md`'s H1.

## Raw numbers — three frozen cohorts, all venture-ON

**Volume & outwardness:**

| cohort | people | speaks | person-addr | city-broadcast | move acts | OUTWARDNESS |
|---|---|---|---|---|---|---|
| on_argmax | 40 | 528 | 209 | 319 | 12 | 39.6% |
| gemini_handonly | 37 | 339 | 181 | 158 | 13 | 53.4% |
| claude_handonly | 32 | 213 | 196 | 17 | 42 | 92.0% |

**Turn-taking band** (A→B answered by B→A within window, % of person-addressed utterances):

| cohort | 5 min | 15 min | 30 min | 60 min | unbounded |
|---|---|---|---|---|---|
| on_argmax | 0.5% (1) | 4.8% (10) | 8.1% (17) | 9.1% (19) | 9.1% (19) |
| gemini_handonly | 28.2% (51) | 30.9% (56) | 32.0% (58) | 32.0% (58) | 32.0% (58) |
| claude_handonly | 5.6% (11) | 8.7% (17) | 11.2% (22) | 15.8% (31) | 15.8% (31) |

**Concentration of the answered utterances @5min window:**

| cohort | answered@5min | distinct dyads | top-dyad share | top dyads |
|---|---|---|---|---|
| on_argmax | 1 | 1 | 100% | Malie↔Tariq (1) |
| gemini_handonly | 51 | 6 | 35% | Gillespie↔Li (18), Gillespie↔Jerome (15), Harper↔Jerome (14) |
| claude_handonly | 11 | 3 | 82% | Meiying↔Giuseppe (9), +2 singletons |

**pair-lenient** ("does the reverse ordered pair occur at all, anytime") = 16–17% across all three —
near-constant, and ~independent of the band above.

## Cohort configs — the confounds, stated plainly

| cohort | seed model | doula mode | venture | targeting | run order |
|---|---|---|---|---|---|
| on_argmax | gemini-3-flash-preview | FULL (seed↔runtime loop intact) | ON | argmax | bench A, **pre**-HAND_ONLY |
| gemini_handonly | gemini | HAND_ONLY (seed loop cut) | ON | — | **post**-HAND_ONLY |
| claude_handonly | claude | HAND_ONLY | ON | — | post-HAND_ONLY |

These three differ on **seed model AND doula mode AND run-length** — no single isolated axis. Nothing
here is a controlled comparison. They are three points that happen to all have venture ON.

## What we are about to run — the venture-OFF arm

A two-slot bench, **≤1 differing axis**: identical Portland, identical dealt-hand seeding, identical
models/chronotype, isolated DBs/feeds — varying only `WW_ACTION_TENDENCY` (venture ON vs OFF). The
first single-axis control venture has ever had. Read with the same `reciprocity.py` + `three_axis`.

There is **no frozen venture-OFF cohort matched to any of the above** — we never saved one. That gap is
why this run exists.

---

## Three asks (you're expensive; these are the high-leverage ones)

1. **Pre-register the falsifier — before we burn the run.** State the result on the OFF-vs-ON bench
   that you would accept as "venture buys engagement" versus "venture buys only outwardness/motion."
   Name the metric, the window, the concentration control, and the threshold delta. Lock it now so we
   can't move the goalpost after we see the numbers.

2. **Spend-gate the run.** Look at the raw above adversarially: turn-taking@5min spans 0.5%→28% with
   venture held ON; the cohort that moved the MOST bodies (claude_handonly, 42) and addressed people the
   MOST (92%) produced near the LEAST real turn-taking (one couple, 82% concentration). **Does the
   frozen evidence already settle whether movement/outwardness produce engagement** — making the OFF
   arm merely confirmatory and not worth the spend? Or is there a real hole only the OFF arm fills?
   Try to break our reading: find the cohort or dyad where moving/addressing DID buy answering.

3. **Design the logging/testing schema (the standing ask).** The recurring failure between rounds is
   that we re-litigate metrics ("CONTACT" meant outwardness; "reciprocity" ranged 0.5%→32% by
   window×concentration; one couple read as 16%). What **minimal event-schema** added to the ledger
   would let you verify reciprocity / contact / casting claims from RAW events alone — your desk
   self-populating from logs, the project's narrative withheld by construction? Current event types in
   the ledger:
   `session_state_observed, ambient_pressure_observed, packet_emitted, surprise_observed,
   trace_verdict_recorded, anchor_observed, baseline_updated, afterimage_cast, pulse_emitted,
   felt_sense_logged, pulse_act_emitted, memory_kept, drive_nudge_cast, ignition_fired,
   self_delta_staged, city_broadcast_sent, idle_fired, venture_target_ranking, move_executed`.
   What's missing such that a contact/engagement claim *cannot* be audited from these alone? And bless
   a single canonical turn-taking definition (window + concentration control) so it stops moving.

---

*Attached: `reciprocity.py` (the instrument) · `raw/3axis_*.txt` (the three CONTACT/VOICE reads) ·
`raw/ledgers_*.tar.gz` (the full ledgers — re-run the instrument, or write your own and try to reverse
the finding).*
