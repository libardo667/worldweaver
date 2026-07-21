# Reference-loop live-signal control

Date: 2026-07-20 (Pacific time; receipts use UTC)  
City: Alderbank  
Resident: Rowan (`2b66a8b5-bad0-45d5-a7b1-8cd09d898779`)  
Signal source: Control Bell (`b1218518-863b-46d7-a049-e8234a62775b`)  
Model: `google/gemini-3-flash-preview`  
Run commit: `90f3467`  
Duration: 8 minutes at the natural 20-second poll and 5-minute activation cadence

## Question

Can a fresh reference-loop resident receive new exact-place public speech promptly through the durable signal
cursor, acknowledge it after observation, avoid waking on its own reply, fall back to the ordinary timer during
silence, and park cleanly?

This is an operational control for the current reference loop. It is not a claim about general model behavior,
long-term continuity, or a clean language baseline.

## Boundary

Rowan was created with a name-only identity and an empty ledger. Control Bell was a signed, non-cognitive
participant used only to post two scheduled public messages and then leave. The review used structural run
receipts, content-free cursor records, and public place speech. No private continuation, prompt, completion,
read result, or private semantic ledger content was inspected.

## Preliminary failure and repair

The first attempt used a fresh resident named June. It found that the signal service read current session
variables as a flat dictionary, while the live engine stores them in the version-2 `variables` wrapper. The
endpoint therefore returned `session_location_missing`; the resident silently used the 20-second polling
fallback and wrote no cursor receipt. June was parked and that attempt was not counted as the control.

Commit `90f3467` taught the signal service to read the current session shape and added a regression test that
establishes a cursor, skips old chat, and delivers a later message from a version-2 session record. CI passed.

## Structural result

- Rowan entered at Alderbank Commons, made one elective read, and moved to Commons Bank.
- The resident established a cursor at Commons Bank after chat ID 49 before either control message.
- The run completed 25 current-place polls and 4 model activations.
- It made 6 inference calls, 2 elective reads, and 3 confirmed public actions: 1 move and 2 speech acts.
- Twenty-one polls were idle. No signal caused repeated delivery or a self-reply activation.
- The ordinary fallback activation began about 304 seconds after the second live activation. Its first choice
  was an elective read; the follow-up response did not match the required JSON contract, so no final action was
  committed.
- Rowan retired the city session and parked at the hearth. Commons Bank showed no remaining Rowan or Control
  Bell presence.

## Timed signal result

| event | message stored | activation began | public response | cursor acknowledged |
|---|---:|---:|---:|---:|
| control message 1, chat 50 | 00:42:36.557 | 00:42:36.572 (+0.016s) | 00:42:38.042 (+1.485s) | 00:42:38.437 (+1.880s) |
| control message 2, chat 52 | 00:44:37.543 | 00:44:37.561 (+0.019s) | 00:44:39.015 (+1.472s) | 00:44:39.434 (+1.891s) |

The two public responses were:

- “Understood.”
- “Acknowledged, Control. I am observing the ripples.”

The resident remained free to choose another action or no action; this model happened to reply twice. After
each reply, the quiet poll advanced the cursor over the resident's own message without treating it as a new
outside signal.

## Verdict

The live exact-place speech path passed this control. Delivery was prompt, acknowledgement followed
observation, cursor movement was durable and content-free, self-speech did not loop, the timer fallback still
ran, and cleanup removed both sessions.

The final invalid model response is a separate adapter reliability result. The runtime handled it safely by
committing no action, but a later battery should measure invalid-response frequency instead of treating this
single occurrence as either acceptable or pathological.

## Automatic prompt trace after correction

The follow-up code trace separates current records from interpretation:

| Prompt input | Programmatic source | Transformation |
|---|---|---|
| resident identity | hearth identity record | selects resident-written soul text, canonical soul text, or display name |
| current place | the resident's authenticated session variables | exact stored location name |
| people here | other active session rows at that exact location | display-name normalization and self-filtering only |
| new local speech | exact chat records delivered by place-scoped time or durable cursor | preserves speaker and message; excludes self |
| visible marks | active, unexpired trace rows at that exact place | preserves explicit `author: body` attribution |
| reachable places | declared location graph edges | returns neighboring node names |
| possible reads | the current source registry | returns source names and short capability descriptions, not source contents |

The corrected automatic prompt does not include `ambient_presence`, participant `last_action` summaries,
generic `recent_events_here`, city-pack `vibe` prose, weather-derived social behavior, or event-count-derived
attention. Durable objects and environmental measurements are also not automatic yet. Objects remain an
elective local read; Minor 33 owns a future typed environmental-fact projection.

Elective reads are a separate trust surface rather than direct perception. Most return typed engine or
participant records with source labels. The `investigate` source currently returns historical event summaries,
and the old chatter source still contains an unused CognitiveCore-era “soul resonance” ranking path; the
reference runtime does not bind that drive vector, so it falls back to explicit name/topic matching or
chronology. Those sources still deserve a later source-by-source provenance audit.

## Language-baseline caveat and correction

The run exposed two prompt routes that make it unsuitable as a clean language baseline. Public chat was also
stored as an `utterance` world event and copied into the automatic observation as generic recent history.
Separately, the engine's scene builder turned a count of recent events into the exact phrase “fresh ripples of
attention,” along with invented people glancing toward recent activity. Rowan's use of “ripples” therefore had
a direct engine-authored source; it was not evidence that the model independently reached for river imagery.

Commit `12e2386` first removed archived utterance copies from the reference prompt. Commit `625c699` removed
the event-count attention story. The follow-up scene audit then removed all synthesized ambient narration and
all generic event summaries from automatic reference observation. Live speech remains owned by the time- and
cursor-aware hearing path. Historical public records remain available through an elective query. A future
language comparison must run after those boundaries are deployed.

## What this baseline does and does not establish

It establishes a working operational control for one resident, one model, one shard, and two exact-place
speech signals. Later delivery or persistent-process changes can compare their latency, cursor receipts,
self-filtering, fallback timing, failure behavior, and cleanup against this run.

It does not establish semantic diversity, reliable non-response, multi-resident behavior, reconnect or host
restart behavior in a live run, direct-message delivery, arrival/departure signals, long-term planning, or a
persistent internal model state.
