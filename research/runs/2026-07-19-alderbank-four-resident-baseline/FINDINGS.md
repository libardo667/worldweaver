# Four residents in Alderbank for one hour — 2026-07-19

## Why we ran this

We wanted to see whether four fresh residents would move around, meet, use the town, and talk without being
given a task. We also wanted a current baseline before changing resident cadence.

The run used the isolated public Alderbank node, not the similarly named development shard in the repository.
It ran from about 5:13 PM to 6:13 PM Pacific time. The four residents were Kim Jun Ho, Kealoha Kalama,
Viktor Sokolov, and Mateo Villalobos. All used `google/gemini-3-flash-preview`, the normal twenty-second
pause, and the optional action-tendency switch.

## Privacy boundary

This report uses the cohort runner's structural summary and speech posted to public places. Public speech is
visible to any person standing there. Private prompts, ledgers, felt sense, hearth writing, information-read
results, and model completions were not reviewed.

The raw run logs remain private and untracked under
`.runs/cohorts/20260720T001344Z-alderbank-public-1/`. The aggregate `summary.json` is the source for the
counts below.

## The run completed safely

- All four residents ran for 3,600 seconds and exited normally.
- All four cleanup operations parked the resident at their hearth.
- No test resident remained in Alderbank's public roster.
- No resident or cohort process remained running.
- Each resident runtime lock was available after cleanup.

## What happened structurally

| Resident | Ticks | Active pulses | Information reads | Model calls | Successful acts | Public speech |
|---|---:|---:|---:|---:|---:|---:|
| Kim Jun Ho | 145 | 57 | 289 | 346 | 37 | 2 |
| Kealoha Kalama | 142 | 57 | 236 | 293 | 29 | 0 |
| Viktor Sokolov | 131 | 56 | 306 | 362 | 35 | 24 |
| Mateo Villalobos | 128 | 54 | 307 | 361 | 8 | 0 |
| **Total** | **546** | **224** | **1,138** | **1,362** | **109** | **26** |

The run used 3,722,424 prompt tokens and 433,966 completion tokens. Every information read caused another
model call in the same pulse: the 1,362 calls are exactly 224 initial pulse calls plus 1,138 read
continuations. This is much more inference than the public activity suggests.

The twenty-second setting is a pause between ticks, not a promise of three ticks per minute. Model calls and
read continuations also take time. That is why each resident completed only 128–145 ticks instead of 180.

All 224 pulses were reactive ignitions. There were no settling, fervor, or venture pulses. The action-tendency
switch therefore never reached the branch it changes and had no effect on this run.

The successful actions were:

- 66 moves;
- 14 concrete `do` actions;
- 3 physical marks;
- 26 public speech acts.

Kealoha moved, acted on things, and left marks without speaking. Mateo moved eight times without speaking.
Public silence did not mean either resident was inert.

## They did cross paths

Presence was sampled every five seconds. At least two residents shared an exact place in 105 of 716 samples,
or about 14.7% of the hour. No sample contained more than two residents.

| Pair | Shared samples | Approximate sampled time |
|---|---:|---:|
| Kealoha and Kim | 67 | 5m 35s |
| Kim and Mateo | 23 | 1m 55s |
| Mateo and Viktor | 16 | 1m 20s |
| Kealoha and Mateo | 15 | 1m 15s |

This proves that a four-resident town can create natural meetings. It also shows why a fixed polling cadence
is brittle: most pairings lasted only a short time, and no public conversation emerged from them.

Residents used a broad part of Alderbank and created or entered smaller places such as Orchard Kitchen,
the studio, and Alder Footbridge. The sublocation work is doing useful work, although inconsistent forms such
as `Orchard Kitchen`, `Orchard Kitchen (Commons Bank)`, and `Orchard Kitchen (Pineward Edge)` show that naming
and parentage still need tightening.

## Public speech was badly uneven

The four residents posted 26 public messages:

- Viktor: 24;
- Kim: 2;
- Kealoha: 0;
- Mateo: 0.

Viktor repeatedly accused unseen people of taking a canvas bag and tools. Ten of his 24 messages mentioned a
bag, eight mentioned canvas, and several repeated the same claim that it could not have walked away. He carried
that story through the Turning Wheel, Alderbank Workshop, and Mill Reach.

Kim's two messages both concerned a missing steel-cased notebook. The first said it had been in a back pocket;
the second described it as a six-year record. No public world event established either missing object.

This is not the older civil-engineering style of monoculture. It may be a new, narrower convergence around a
missing possession. One hour and two speaking residents are not enough to call that a population result, but
it is enough to investigate before a larger run.

## One concrete loop bug was found and fixed

City sessions are temporary. A resident gets a new session after going home and returning. The hearing code
filtered out messages from the current session but did not filter the same resident's older session. A
returning resident could therefore hear their own earlier public speech as if somebody else had said it.

That failure was visible in this run: Viktor's early chat rows used an older session ID, while later rows used
his new session. The older rows had also lost their actor ID when the temporary session was retired.

Commit `aff235f` fixes both sides:

- new public chat rows keep the author's durable actor ID even after the city session is retired;
- resident perception filters its own durable actor ID across sessions;
- legacy rows without an actor ID use an exact own-name fallback;
- a different actor with the same display name is still heard when its actor ID is available.

The full engine and resident test suites pass, and a clean database upgraded through the new migration.

This bug can explain why Viktor's first unsupported story became a long loop. It cannot explain why Viktor or
Kim invented a missing object in the first place.

## The hearth/workshop boundary is another real lead

A resident uses the same private workshop in the city and at their hearth. The current pulse prompt shows a
summary and excerpts from that workshop in either place. It describes the workshop as something the resident
"holds" and lists journals or projects by name.

Physical city objects work differently. A resident must elect to inspect the `objects` source to see what they
carry or what lies at the current place. The prompt does not explicitly say that a private notebook or project
remembered from the workshop is safely stored at home rather than physically present in a pocket.

That mismatch makes the user's hypothesis plausible: a model may see a remembered notebook or other private
making, fail to see it in the current room, and turn absence from immediate perception into loss. We did not
read the residents' private workshop contents, so this run cannot prove that Kim's notebook came from a real
private artifact. It does show that the architecture currently leaves the distinction unclear.

## What to change before the next large run

1. Deploy the self-hearing fix to isolated Alderbank.
2. Make attachment and possession explicit in prompt context: private workshop records are available to the
   resident but are not automatically physical objects being carried; an object not shown in the current scene
   is unknown, not missing.
3. Give exact-place direct speech and new co-presence a cheap wake signal. Let them cause an earlier perception
   tick without forcing a reply.
4. Put a firm budget on information-read continuations. Six model calls per active pulse is too expensive and
   leaves the resident reading while short meetings pass.
5. Tighten sublocation identity so one room does not appear under multiple parent labels without an actual
   move or transfer.
6. Repeat the same four-resident run after those changes. Keep model, duration, and residents fixed so the
   comparison means something.

The next test should measure whether meetings lead to perceived speech and replies, not merely whether two
session rows shared a location. Public wording can again be checked with aggregate repetition counts and a
small number of cited public examples; private prose should remain closed.
