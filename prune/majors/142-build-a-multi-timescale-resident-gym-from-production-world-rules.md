# Build a multi-timescale resident gym from production world rules

## Problem

Short prompt examples can teach a model to emit valid JSON, but they cannot show whether a resident maintains
a plan, resumes after interruption, distinguishes live events from history, adapts to delayed consequences,
or changes through experience. Running every candidate for real days or years would be too slow and expensive.

A separate toy simulator would create a worse problem: models would learn its shortcuts and then meet different
rules in a live shard. The gym must therefore reuse the same action validation, receipts, event formats,
permissions, object custody, travel rules, and resident-process contract used in production.

## Proposed Solution

Build a discrete-event training and evaluation environment around the real WorldWeaver contracts. It should
run conversations and short-lived conflicts at real or measured interactive speed, then skip quiet wall-clock
periods by advancing an injected clock directly to the next scheduled event.

1. Give engine and resident time-dependent code one injected clock and event queue. Production uses real UTC;
   the gym uses controlled virtual time. No test-only alternative physics or action handler may replace the
   production rule path.
2. Support mixed-time episodes: live conversation, interruption, and competing actions in seconds; reading,
   appointments, projects, correspondence, travel, and delayed consequences over virtual days or years.
3. Snapshot and fork complete synthetic states. Run matched branches in which one event changes while the
   resident, model, seed, and prior history stay fixed.
4. Build scenario generators from validated city packs and rulesets. Vary geography, access, objects,
   schedules, failures, missing information, social density, and participant implementations without writing
   a host-authored personality for the resident.
5. Use scripted actors, small policies, and deterministic environment processes for most background activity.
   Use additional language-model residents only where their behavior is part of the question.
6. Record complete synthetic structural trajectories: observation version, event delivery, resident choice,
   attempted action, canonical receipt, elapsed time, checkpoint version, interruption, and later consequence.
   Do not require or import private prose from real residents.
7. Score separate competencies rather than one engagement reward: state grounding, action validity,
   uncertainty, plan revision, interruption recovery, timing, permission handling, and consistency. Waiting,
   reading, abandoning a plan, or remaining silent may all be valid.
8. Run many independent resident states against shared model weights through batched inference. Training speed
   comes from parallel episodes and skipped quiet time, not from weakening the world rules.
9. Publish a held-out benchmark with unseen cities, paraphrased observations, renamed internal fields,
   different event orderings, and repeated trials. Keep the training scenarios separate.

### Current boundary finding and completed prerequisite extraction — July 20, 2026

The first source audit found an uneven production seam. Object custody, making, access, exchange, and stoops
already put most business rules in service modules below HTTP. The first extraction moved canonical place
anchoring into `services/location_routes.py` and the complete movement rule path into `services/movement.py`.
The live HTTP endpoint now authenticates, calls that service, and translates its typed receipt or refusal.

Local speech now lives in `services/local_speech.py`; its route authenticates and translates the service's
typed receipt or refusal. Session entry and retirement now live in `services/session_lifecycle.py`. Inter-city
travel now lives in `services/shard_travel.py`; its route gathers exact human or resident proof and translates
typed service receipts.

Movement revealed that its session-state save and movement-event write were separate commits. That follow-up
is repaired: deferred event submission stages enabled projections and graph facts in the caller's transaction,
movement stages its final session state, and one commit covers the complete single-hop or skip-through command.
Tests force both an ordinary event failure and a final-hop failure and prove that database and cached state
return to the origin.

Local speech exposed the same class of fault in a more visible form. The chat row was committed and waiters
were notified before the canonical utterance event was attempted; every event failure was then silently
ignored. The service now commits the chat row, utterance event, projection, and fact together and notifies
waiters only after success. A forced event failure proves that no chat row or event remains and no false wake
is sent.

Session bootstrap exposed an append-only violation: its duplicate-agent cleanup deleted the older session's
public events and facts. It now retires only the stale live presence and preserves public history. Bootstrap
also refuses to overwrite an occupied session ID and commits the new state, bootstrap event, account or
resident authority binding, and duplicate retirement as one local transaction. Tests force event and resident
binding failures and prove that neither a half-created session nor a half-created arrival event survives.

Travel exposed the distributed version of the split-write problem. The federation could confirm a departure
or arrival, the local handoff could be marked complete, and then a best-effort local event could fail forever.
The service now keeps the local handoff in its prior retryable state unless the local status and event commit
together; retrying an already-confirmed remote transition is safe. Tests force both final-event failures and
prove that retry produces one event. The extraction also found that travel routes ignored resident signatures
and destination bootstrap did not bind the new session to the active resident generation. Initial departure,
retries, and arrival now require human login or exact resident proof, and verified resident arrival creates or
repairs the destination session binding.

Do not start the fast gym by calling route functions, copying those rules, or writing synthetic state directly.
The prerequisite production seam now exists for a first episode. Build the smallest deterministic adapter over
the services, then repeat that same episode through HTTP and compare receipts before adding accelerated time,
forking, model calls, or training data. The maintained dependency atlas and the plain-language episode design
live in `docs/reference/dependency-atlas.mdx`.

### First executable episode — July 20, 2026

`python dev.py gym` now runs `The Footbridge Hello` against a temporary database. A scripted participant and
a mechanical listener enter through session bootstrap, establish present-time speech cursors, exchange local
speech, walk apart, prove that speech at the old place does not follow the listener, and resume delivery after
they meet again. The adapter calls `bootstrap_session`, `post_local_speech`, `move_session`, and
`read_live_signals`; it contains no alternate action or perception rules.

The command prints a compact structural timeline and writes a self-contained HTML view under `.runs/gym/`.
Both views use only synthetic utterances, service receipts, and signal reads. Their icons and layout are
presentation, not narrator-authored events. The mechanical listener is a transparent fixture, not a model
resident and not a preferred behavior policy.

An automated conformance test now repeats the episode through FastAPI with two separately registered human
actors. It verifies that an anonymous signal read is refused, supplies each actor's bearer token, and compares
the resulting chat rows, world events, and final locations with the service-level run. They match. This is
in-process HTTP parity, not a container or public-network proof.

Next, extract and repair the current direct-message routes so delayed correspondence uses the same shared
boundary. Do not add controlled time, checkpoint forks, model calls, or training records until correspondence
has production-service and HTTP coverage of its delivery and acknowledgement rules.

## Files Affected

- `worldweaver_engine/src/services/state/`
- `worldweaver_engine/src/services/action/`
- `worldweaver_engine/src/services/simulation/`
- `worldweaver_engine/src/services/map_generation/`
- `worldweaver_engine/tests/`
- `ww_agent/src/runtime/`
- `ww_agent/tests/`
- `research/resident-gym/` (new)
- `scripts/` (new gym operation commands)
- `docs/reference/architecture.md`
- `docs/reference/dependency-atlas.mdx`
- `docs/reference/resident-gym.md` (new)

## Acceptance Criteria

- [ ] The same production domain functions decide an action in a live test shard and in the gym.
- [ ] One episode can combine sub-minute conversation with multi-day scheduled activities without sleeping
  through the quiet virtual interval.
- [ ] Synthetic snapshots include enough engine and resident state to fork, replay, stop, and resume an
  episode with documented determinism.
- [ ] Scenario actors cannot bypass the public participant protocol or write authoritative state directly.
- [ ] The suite covers live speech, deliberate delay, interruption, stale information, uncertain outcomes,
  object custody, access refusal, correspondence, travel, and a later consequence of an earlier choice.
- [ ] Evaluation gives no general reward for speaking, moving, pleasing a human, finishing every plan, or
  producing dramatic output.
- [ ] At least two different participant implementations can run in the same episode.
- [ ] Training and held-out city packs, scenarios, seeds, and model versions are recorded separately.
- [ ] A counterfactual fork can show whether one changed event caused a later change without reading private
  prose.
- [ ] Gym trajectories contain only synthetic or explicitly licensed material and retain their generation and
  model provenance.

## Risks & Rollback

Accelerated time can hide latency, race conditions, or costs that matter in a live city. Keep measured real-time
windows and repeat important scenarios against an actual containerized shard. A fast simulation is evidence
about the contracts it exercises, not proof of live operational performance.

Scenario generators can also encode one developer's idea of desirable behavior. Keep scoring structural,
preserve multiple valid outcomes, publish scenario assumptions, and reject any benchmark that quietly equates
visible activity with a better resident. If production and gym rules diverge, stop training on the gym until
the shared boundary is restored.
