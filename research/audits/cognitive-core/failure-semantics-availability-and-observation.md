# Failure semantics, availability, and observation

Status: code audit, 2026-07-19. No live resident prose was read for this pass.

## Plain result

The runtime is designed to keep its process alive when a service fails. That is useful. But it often does so
by turning “unavailable,” “unknown,” or “may have happened” into an ordinary value such as empty, neutral,
daytime, not executed, or observed.

This makes the process resilient while making its records less truthful. A resident can be prompted with an
old scene after the current scene failed to load. A temporary grounding failure can remove the night-time
cadence multiplier. A failed model call can consume the pressure that caused the call and mark included chat
as observed. A network timeout after an action request is treated as proof that the action did not happen,
even though the remote shard may have committed it.

The missing concept is explicit uncertainty. WorldWeaver needs separate states for:

- successfully observed present;
- successfully observed absent;
- not observed because the source was unavailable;
- stale information from an earlier successful observation;
- action confirmed;
- action declined;
- action outcome unknown after transport failure.

Without those distinctions, later behavioral results cannot be attributed to the cognitive policy rather
than to invisible service failures and stale caches.

## Current failure conversions

| Boundary | Failure conversion | What later code believes |
| --- | --- | --- |
| scene fetch | `perceive()` returns `{}` at debug log level | the scheduler continues from existing ledger state; the prompt producer retains its prior scene and images |
| local chat fetch | catches the error and uses `messages = []` | old pending packets remain, but current source availability is unknown and unreported |
| inbox fetch | catches the error and returns count `0` | unavailable is represented as no newly fetched mail |
| grounding fetch | returns `{}` | the current tick uses reactivity `1.0`, regardless of the previous or actual local night state |
| embedding setup | marks construction attempted before the request; failure does not retry | semantic drive remains off for that core lifetime, while memory retrieval keeps a failing embedder object |
| initial model call | returns `None` on transport or validation failure | ignition or idle is still recorded as spent; content-blind metrics do not say the completion failed |
| continuation model call | returns `None` | the pre-read pulse is routed after its reach is stripped, even though no valid post-read decision exists |
| world action transport | broad catch returns `executed: false, reason: exception` | a timeout is treated as a confirmed non-event rather than an unknown remote outcome |
| whole tick | exception is logged, followed by ten seconds plus normal cadence | no durable structural event explains the missing tick or changed delay |

These fallbacks were mostly added for understandable local reasons. Together they create a runtime where
“nothing happened” is often indistinguishable from “we do not know what happened.”

## A scene failure leaves the old scene inside the model

`CognitiveCore.tick_once()` updates `LLMPulseProducer.latest_perception` and `pending_images` only when
`perceive()` returns a non-empty brief. On a scene-fetch exception, `perceive()` returns `{}`.

The core clears the effector's co-presence and heard lists, which prevents one class of stale outward routing.
It does not clear or mark stale:

- `LLMPulseProducer.latest_perception`;
- `LLMPulseProducer.pending_images`;
- the previous prompt's location, recent events, workshop context, source catalog, and reachable places stored
  in that perception dictionary.

The integrator then continues. It derives numeric stimulus from the existing ledger and may open a reactive,
settling, fervor, or venture call. If it does, prompt construction uses the previous successful scene. A
vision-capable reactive call can also resend the previous scene's image.

This is not a safe “last known state” policy because the prompt does not label the material stale or name the
failed observation. It presents it as the current waking moment.

The repair is not to replace a failed fetch with an empty room. Empty is also an observation claim. Instead:

1. record a content-blind observation attempt and result;
2. retain last-known state with its original timestamp if useful;
3. mark every retained field stale;
4. prevent stale co-presence and action targets from being treated as current;
5. decide explicitly which self-directed operations may continue while the world is unavailable.

## Model failure consumes both scheduler pressure and social delivery

The initial pulse path currently performs this sequence:

1. build the prompt from selected pending packets;
2. save those packet IDs on the producer;
3. call the model;
4. if the call fails or its JSON is invalid, return no pulse;
5. record `ignition_fired` anyway, resetting accumulated surprise, or record `idle_fired` for a quiet-time
   attempt;
6. write `pulse_runtime_summary` with `model_calls: 1` but no completion-success field;
7. take the saved packet IDs and mark them `observed`.

Existing tests deliberately require the ignition reset. It fixed a real failure mode in which a broken model
endpoint left pressure above threshold and the resident spun forever. But call backoff and stimulus delivery
were made into the same state transition. Preventing a retry storm now also consumes the event that needed
attention.

For a direct message, this can mean:

```text
message queued
    -> included in attempted prompt
    -> model request fails or response is invalid
    -> message marked observed
    -> call pressure reset
    -> no valid pulse and no pending message
```

Whether an HTTP request reached a provider is also not the same as whether a valid model response processed
the message. “Prompt assembled,” “request sent,” “completion received,” “completion validated,” and “packet
observed” need separate receipts.

The right fix is not immediate unlimited retry. Keep a host backoff and failure budget, but leave the source
packet pending until a valid prompt episode commits or the resident explicitly ignores, defers, or expires it.

## A failed continuation commits the pre-read response

The private read loop has conditional authority that the contract does not describe.

On a successful continuation, the new full pulse replaces the pre-read pulse. Its expectations, memories,
self-report, and identity proposal become the final values.

If the continuation returns no valid pulse, `_reach_then_act()` instead removes `reach` from the pre-read pulse
and returns the rest of that older object for normal routing. The same pre-read fallback occurs when the read
budget is zero, the information boundary is unavailable, or a read is deduplicated.

This means a model can:

1. ask to inspect a source while also filling in predictions, memory, and identity fields;
2. receive the source result in a continuation request;
3. fail to return a valid continuation;
4. still have its before-reading predictions, memories, and identity proposal committed.

The ledger can separately say that information was accessed, even though there is no valid after-reading
response. The transaction has no honest single meaning.

Read requests should therefore use a provisional response type that cannot contain durable fields. Only a
validated final response should commit predictions, memory, self-report, identity proposals, or an act. If a
continuation fails, the episode should end as failed after a bounded retry policy; it should not promote the
pre-read draft.

## A model call and a successful model call are not distinguished

`pulse_runtime_summary` is described as a content-blind operational receipt. It currently reports call count,
elapsed time, read counts, outward-act presence, and action outcome. It does not report:

- whether the initial completion arrived;
- whether JSON validation passed;
- how many continuation calls failed;
- provider/model identity as actually resolved;
- retry count or backoff;
- token use or estimated/actual cost on this path;
- which packet-delivery stage was reached.

Exact prompt tracing does record completion failures and validation rejections, but it is optional diagnostic
state, contains private prose, is excluded from portable hearth packages, and should be off by default. The
only way to understand a failed run should not be to enable broad private capture.

A small structural inference receipt belongs in the canonical ledger. It should name no prompt content. It
should say request ID, model/provider policy ID, start/end time, status, validation status, token/cost counters
when supplied, associated activation ID, and retry/backoff decision.

## Grounding failure changes the resident's cadence

The grounding helper catches a time/weather failure and returns no current value. `tick_once()` initializes
reactivity to `1.0` and changes it only when the returned perception brief contains wakefulness. Because a
scene can succeed while grounding fails, the rest of the brief remains valid and the tick proceeds at full
reactivity.

This makes a temporary weather/time endpoint failure a hidden cognitive-policy change. A night-time resident
can receive daytime call pressure for that tick. The durable rest reducer may still carry the last successful
circadian observation, so the same tick can combine old night state in one projection with current default-day
reactivity in another.

The immediate software repair is to treat cadence grounding as present, stale, or unavailable and apply one
declared fallback consistently. The larger audit has already found that this is only a clock multiplier and
should be named as such rather than sleep or physiology.

## Embedding failure creates a sticky mixed configuration

`_ensure_drive_vector()` sets `_drive_built = True` before it contacts the embedding service so that a broken
endpoint cannot create a retry storm. It also attaches `MemoryRecall` to the same embedder before the drive
build completes.

If the first drive build fails:

- the drive vector stays absent and is not retried during that core lifetime;
- citywide semantic chatter ranking is never bound;
- resonance and destination ranking fall back;
- memory recall and keepsake dedup still try to call the failing embedder on later pulses and quietly fall
  back when those calls fail.

The runtime is therefore neither cleanly “embedding off” nor “embedding on.” A transient startup failure can
create a mixed policy until attachment change, restart, or identity adoption rebuilds the core state.

Provider health, retry backoff, and active cognitive policy must be separate. On failure, either disable all
embedding-dependent policy under one recorded state or retry the provider under a bounded circuit breaker.

## Network uncertainty is reported as action failure

`WorldEffector.__call__()` catches every exception from speech, movement, writing, object, access, stoop, and
other effectors and returns:

```text
executed: false
reason: exception
```

For a local validation exception, that may be accurate. For a distributed write, it may not be. A request can
reach a shard, commit, and then lose its response. In that case the host does not know whether the action
happened. Object and access commands carry idempotency keys, which can support resolution. Ordinary speech,
movement, and some correspondence paths do not all expose the same transaction guarantee.

The action lifecycle needs at least `confirmed`, `declined`, and `unknown`. An unknown write should retain its
idempotency key or request ID and reconcile with the shard before a retry. Reporting it as definitely not
executed can make the resident repeat an already-completed action or remember a false failure.

## There are two core run loops, but only one is live

`CognitiveCore.run()` contains its own infinite tick loop and error delay. The actual resident runtime does not
call it. `Resident._run_started()` implements a second loop around `core.tick_once()` so it can handle travel,
mirroring, bounded runs, observers, and hearth attachment.

The unused loop is not causing current behavior, but it is another misleading surface. A future caller could
reasonably use it and get different force-attention, travel, lifecycle, and failure behavior. The core should
offer `tick_once()` only, or there should be one shared runner with explicit policies.

## Required repairs before another resident trial

1. Add explicit availability and freshness to every observation boundary.
2. Clear or stale-label prompt caches and images when current perception fails.
3. Separate model-call backoff from packet delivery and scheduler stimulus lifecycle.
4. Mark a packet observed only after a declared valid delivery stage; retain explicit defer, ignore, and
   expiry states.
5. Replace full provisional pulses with a read-request type and commit only a valid final response.
6. Write content-blind inference attempt, completion, validation, retry, and failure receipts to the ledger.
7. Give distributed actions an `unknown` outcome and reconcile idempotent requests.
8. Make embedding policy atomic and observable under provider failure.
9. Remove the unused `CognitiveCore.run()` loop or route every runtime through one runner.
10. Test scene, grounding, inbox, chat, embedding, inference, continuation, and post-response failures without
    reading resident prose.

These are software correctness requirements. They do not depend on choosing a theory of mind.
