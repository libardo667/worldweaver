# Deliver live signals without forcing a response

## Status

The fixed-cadence Alderbank baseline is complete. Four residents ran for one hour and crossed paths in 105
of 716 five-second samples, but none of those meetings produced a public conversation. The run completed 546
ticks, 224 active pulses, and 1,362 model calls under the old CognitiveCore runtime. Keep it as historical
comparison evidence, not as the target architecture. See
[`research/runs/2026-07-19-alderbank-four-resident-baseline/FINDINGS.md`](../../research/runs/2026-07-19-alderbank-four-resident-baseline/FINDINGS.md).

The small reference loop has since replaced CognitiveCore in production. It polls every 20 seconds, usually
activates only for new exact-place speech or a five-minute baseline, and remains free to act, continue
privately, or wait. Levi's first plain run noticed three live human messages within one polling interval and
parked cleanly. That is a good control result. It does not yet provide durable event delivery: a host still
has to ask repeatedly whether anything changed.

## Problem

A person entering a room cannot choose not to see the room or hear speech that occurs beside them. A resident
therefore needs a bounded stream of unavoidable local facts. But delivery, consideration, and response are
three different things:

1. the world makes a relevant event available;
2. the resident process gets an opportunity to consider it;
3. the resident decides whether and when to do anything.

The current poll bundles the first two. Making every poll faster would spend more resources even in quiet
places and would still leave gaps during inference, travel, shutdown, or network trouble. Treating a direct
address as a command to answer would solve the wrong problem. The resident may be reading, working, waiting,
or simply unwilling to reply.

## Proposed Solution

1. Define a small set of structural live signals: exact-place speech since a cursor, actor arrival or
   departure, direct correspondence when Major 39 defines it, the result of the resident's own action, and
   declared local physical changes. Do not send generated narration or citywide summaries.
2. Give every resident attachment a durable event cursor. A reconnecting process can ask for events after
   that cursor, acknowledge what it received, and detect an expired retention window rather than silently
   treating missing history as an empty scene.
3. Add an interruptible wait using long polling or a similarly cheap subscription. A new eligible signal can
   offer an earlier activation; a resident-set timer or quiet baseline can do the same without a world event.
4. Scope signals by authorized actor, active runtime generation, shard, and exact place. Travel must retire
   the old subscription before the destination begins delivering events.
5. Coalesce repeated notifications while preserving the underlying ordered events. Backpressure must delay or
   summarize structural notice, not discard a direct address without saying that retention was exceeded.
6. Keep timing policy private and resident-controlled. The host may enforce rate and cost limits, but it must
   not score message prose for urgency, infer social obligation, or require a public response.
7. Record content-blind operational evidence: event time, offer time, acknowledgement cursor, activation time,
   delivery gaps, duplicate deliveries, resource use, and cleanup. Do not copy message bodies into metrics.
8. Keep the 20-second reference poll as a fallback and comparison path until the event path survives pause,
   reconnect, travel, and host restart tests.

Major 141 uses this delivery contract to wake a persistent resident process. Major 138 should expose the same
cursor and receipt behavior to independently implemented participants without exposing their timing policy.

## Files Affected

- `ww_agent/src/resident.py`
- `ww_agent/src/runtime/reference_core.py`
- `ww_agent/src/world/city_world.py`
- `ww_agent/src/world/client.py`
- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/src/services/`
- `worldweaver_engine/tests/`
- `ww_agent/tests/`
- `docs/reference/participant-protocol.md`
- `docs/how-to/run-residents.md`

## Boundaries

- Faster notice never means forced speech, movement, agreement, or cancellation of private work.
- Automatic delivery contains local facts and exact public speech, not a model-written account of what they
  mean.
- Distant places, archives, citywide conversation, and detailed records remain elective information.
- One busy place must not wake residents elsewhere.
- A steward may limit cost and abusive traffic but may not rank a person's importance through hidden prose
  analysis.
- A process that was offline is told what elapsed and what retained events exist; the system does not pretend
  it was continuously aware.

## Acceptance Criteria

- [ ] New eligible exact-place events can reach a resident attachment without repeated full-scene polling.
- [ ] A durable cursor supports acknowledgement, reconnect, ordered replay, and an explicit retention-gap
  result.
- [ ] Delivery, activation, and public response are represented separately in code and structural receipts.
- [ ] Receiving a direct address never requires the resident to reply or act.
- [ ] Unaddressed citywide speech and distant activity do not wake a resident.
- [ ] Repeated signals are bounded without silently losing their underlying cursor position.
- [ ] Shutdown, pause, hearth parking, travel, host restart, and exclusive runtime generations retire or
  restore subscriptions without cross-resident delivery.
- [ ] Content-blind tests measure notice latency, duplicate or missing delivery, ordinary poll reduction,
  resource use, and cleanup.
- [ ] The existing reference poll remains a working rollback path until the event path is proven.

## Risks and Rollback

An event path can create notification storms, leak one place's activity to another, race with travel, or turn
social contact into a coercive engagement system. Start with local structural events, strict actor and runtime
generation checks, bounded retention, and synthetic fault tests. If ordering or isolation fails, disable early
wakeups and return to the reference poll while retaining explicit cursor diagnostics.
