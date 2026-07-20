# Elective information and resident agency

Status: code audit and deterministic reproductions, 2026-07-19.

This pass asks a simple question: can a resident choose to spend a long time reading or investigating, or can
it only choose among a few reads after the host has already decided to wake it?

The answer today is the latter. The named information sources are a useful capability boundary, but the
runtime around them supports short reactions rather than durable, self-directed inquiry.

## What actually happens

1. Python polls the current world and reduces observations into call pressure.
2. Python decides whether to open a model call because of reaction, settling, fervor, venture, or an explicit
   forced wake.
3. Only inside that call can the model return a `reach` request for one advertised information source.
4. Python reads the source and opens another model call with the result.
5. The model may read again, act once, or end the episode.
6. Python routes only the last returned `Pulse` into durable pulse state and the world effector.

The resident therefore chooses *what* to read inside a waking episode. It does not choose *when* to resume
an inquiry while no model is running, because there is no resident process between model calls and no live
durable inquiry state for the scheduler to resume.

For an LLM-based resident, “reading all day” cannot mean that one hidden mind keeps running between API calls.
It has to mean a sequence of model calls connected by durable state: an inquiry the resident chose, a place
to resume, a resource envelope, and opportunities to pause, continue, abandon, or attend to a new event.
WorldWeaver does not yet have that sequence.

## What the resident can currently read

Every embodiment can offer:

- `recall`: selected kept memories and prior model self-reports;
- `measure`: bounded arithmetic.

A hearth may additionally offer `growth`, delivered `gifts`, and read-only `files`. File access is constrained
to explicitly configured roots, follows ignore rules, denies common secret paths even when a project forgot
to ignore them, rejects path escape, and caps one text-file window at 40 KB.

A city can additionally offer `places`, `surroundings`, `investigate`, `chatter`, and `travel`. Depending on
the shard's advertised capabilities it may also offer `objects`, `making`, `exchanges`, `access`, and `stoops`.
The legacy San Francisco catalog adds `eats` and `news`.

This registry is a good separation of powers: a world explicitly contributes sources, and a private read does
not masquerade as a physical world action. The problems below are in scheduling, continuation, persistence,
time, and policy—not in the basic idea of named, capability-scoped sources.

## The current read cap is an emergency rail, not attention

Commit `87a70de` changed the old six-read loop to a default host maximum of two reads per active pulse, with
an absolute ceiling of eight. That was a current project intervention made after a run spent excessive time
and calls reading. It was not inherited evidence about how attention ought to work.

The limit is a read count, not a true resource budget. At the default of two reads, one episode may use three
model calls: the initial pulse plus one continuation after each read. Each continuation uses the ordinary
model output ceiling, and source results may contribute up to 4,000 characters apiece to continuation prompts.
Input size, output tokens, wall time, and model price may vary substantially while the read count stays two.

The source comments that call this a “single LLM call” architecture are therefore false once a reach occurs.
The honest unit is one *activation episode*, which may contain several inference calls and yields one final
pulse.

A steward still needs a hard way to stop runaway cost and latency. That host concern should be named and
reported as a resource envelope or circuit breaker. It should not silently become the resident's attention
policy or an argument that continued reading is unhealthy.

## Continuation is lossy

Each continuation returns the full `Pulse` schema, but the integrator replaces the prior pulse with the new
one. Only the final pulse is routed. An expectation, keepsake, identity proposal, drive nudge, trace verdict,
or felt report returned before another read is discarded unless the model happens to repeat it later.

A deterministic run returned a keepsake and afterimage in the initial read request, then returned an empty
final pulse after seeing the result. The runtime reported two model calls, logged only the final felt report,
and persisted neither the initial keepsake nor the initial afterimage.

Final-only commit semantics can be a sound design, but the current full-schema continuation prompt does not
explain that earlier fields are provisional and will be lost. The implementation should either:

- use a smaller continuation schema and make final-only commit explicit; or
- merge explicitly durable choices across the episode with clear conflict rules.

It should not invite durable fields at every step and silently retain only the last set.

## Duplicate suppression can end a thought without returning the result

Equivalent source, kind, and query requests are cached for 30 seconds by default. On a cache hit, the
integrator stops the reading chain without making another continuation call. That is reasonable if the model
in the current episode has just seen the same result. Across two separate pulses, however, the second model
may request the same source without having the prior raw result in its prompt. The request is then closed and
the cached result is never presented to that model call.

The cache also ignores the `now` value passed into information access. A deterministic reproduction made the
same request with supplied times ten years apart; the world provider was called once and the second request
was marked as a fresh duplicate because only `time.monotonic()` was consulted. Replay behavior therefore
depends on how quickly the test computer executes, not the replay clock.

The cache lives only in one `InformationAccess` object. Rebuilding the core after a restart or shard transfer
clears it. The same logical sequence can consequently behave differently across process and travel boundaries.

Cache reuse should either return the cached result through the normal continuation path or produce an explicit
model-visible outcome. Its clock should be injected for deterministic replay, and its lifetime should be
described as a host optimization rather than resident memory.

## The waking moment mixes frozen and live time

The continuation prompt says the world is frozen from the initial prompt. More precisely:

- the initial scene, people-present list, navigation list, and advertised source catalog are retained;
- a selected source may fetch live shard state when the read executes;
- the eventual world action is sent to the live engine, which may accept or reject it under current rules.

That is a mixed-time transaction, not a frozen world. A slow multi-call episode can reason from stale presence
while receiving a newer tool result. The prompt and receipts should expose snapshot times or revisions instead
of promising a freeze the engine does not provide.

## The prompt still confuses attention with response

The shared pulse rules say to choose a non-null act when someone addresses the resident. That is stronger than
making the words available to attention. A reliable event path should let the resident notice an address and
then speak, act, defer, refuse, keep reading, or do nothing. The host may guarantee delivery; it should not
turn delivery into mandatory outward behavior through prompt wording.

This matters for sustained inquiry. A durable reading task needs interruption, not command obedience:

- surface the new event without losing the current place in the inquiry;
- let the model decide whether to switch focus;
- retain the unfinished inquiry when it switches;
- do not infer a duty, disorder, or lack of care from deferral or silence.

## There is no durable inquiry control state

The pulse schema appears to have candidate fields for longer-lived self-direction, but they do not currently
provide it:

- `self_delta.goal_update` and `self_delta.new_reverie` are stored as staged events with no production reader;
- `drive_nudges` are stored and can be reduced, but the reduced value has no production consumer;
- keepsakes preserve facts and genuine decisions, while the prompt explicitly rejects reminders and
  instructions to oneself;
- `research_queued` is reducible ledger state, but no production writer starts that lifecycle.

After a final `act: null`, the next model opportunity comes from later call-pressure policy, a periodic host
mode, or a forced wake. Nothing says “resume the chapter I chose,” “continue comparing these records,” or
“leave this inquiry open until I decide it is done.”

This creates a structural bias toward short reactions and completed outward acts even if the model would have
preferred a long period of study. Raising the numeric cap would make episodes more expensive but would not
repair that missing continuity.

## Better separation of responsibilities

The next design should keep four concerns separate:

1. **World permission:** which sources and records this resident may access here.
2. **Resident choice:** what inquiry to begin, continue, pause, abandon, or finish.
3. **Event attention:** which new embodied events must be made available, without forcing a response.
4. **Host resources:** the transparent limits on calls, tokens, wall time, concurrency, and money.

A first implementation does not need a theory of human attention. It needs an honest task lifecycle, for
example `inquiry_started`, `inquiry_checkpointed`, `inquiry_paused`, `inquiry_resumed`, and `inquiry_closed`,
with source references and structural progress rather than hidden chain-of-thought. The scheduler can then
offer a resident-chosen continuation opportunity within the steward's published resource envelope.

The resident should be able to use that opportunity to continue reading, switch to an embodied event, act,
or remain quiet. The resulting policy can be tested without declaring any one distribution of those choices
healthy.

## Required tests before interpreting behavior

- Repeated reading across several scheduled episodes, including pause and resume.
- The same sequence under a virtual clock, natural cadence, and bounded smoke cadence.
- A direct address during an open inquiry, with delivery separated from reply.
- Source data changing between reads, with revisions or timestamps visible.
- Core rebuild and shard travel while an inquiry remains open.
- Host budget exhaustion that pauses rather than silently completes the inquiry.
- Cached and uncached reads that present equivalent information to the model.
- Intermediate continuation fields, with explicit final-only or merge behavior.
- Cost comparisons based on actual calls, tokens, latency, and model price—not read count alone.

Until those exist, the two-read default should remain described only as a temporary circuit breaker. It is
evidence that the host can bound a call chain, not evidence that the resident controls its waking attention.
