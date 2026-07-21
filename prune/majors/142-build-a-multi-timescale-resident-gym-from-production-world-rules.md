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

The correspondence prerequisite is now extracted and repaired. Local private messages are addressed to durable
actor IDs, require exact human or signed-resident proof, remain pending when read, and disappear from the
pending inbox only after explicit recipient acknowledgement. The old unauthenticated name- and session-based
routes return `410 Gone`. The reference resident sees pending correspondence during an activation, records no
private message prose in its runtime evidence, and acknowledges only after successful inference. Unknown names
are refused rather than guessed as recipients.

`python dev.py gym --episode waiting-letter` now exercises that boundary. Mara sends a synthetic letter, Ivo's
temporary session ends, and Ivo returns under a new session with the same durable actor ID. Two reads return the
same waiting letter, explicit acknowledgement consumes it, and the final read is empty. The HTML view presents
the service states as a small animated post trail; the animation adds no world event. Cross-shard delivery and
the human correspondence interface remain open.

The first clock slice is now executable. `python dev.py gym --episode quiet-interval` begins with normal
exact-place speech, creates a production ephemeral sublocation with a two-day lifetime, advances a controlled
aware-UTC clock by 47 hours, verifies the place remains active, advances two more hours, and verifies expiry.
The clock refuses backward movement, the live default remains real UTC, and no process sleeps through the
interval. The report marks exact timestamps and clock jumps without inventing an event.

The first scheduler slice now replaces the episode's manual jumps. Scheduled events have stable IDs, sort by
UTC deadline and insertion order, remain pending until explicit acknowledgement, and serialize with the
controlled clock into a versioned JSON-safe checkpoint. Restore re-offers an unacknowledged due event with the
same ID, while acknowledgement prevents later redelivery. This is deliberately at-least-once; future mutating
handlers must carry the event ID into production idempotency keys.

The reference resident now exposes a content-free schedule for its next chosen private return. The schedule is
derived from durable private-ledger state, survives runtime reconstruction, and contains only a stable event ID,
activity ID, and UTC deadline—not the activity prose. A two-day synthetic check reconstructs the resident,
advances directly to the deadline, activates it, and proves the scheduled return is consumed once.

The first combined restart envelope is now in place. It binds scenario ID/version/seed, participant identities
and adapter versions, signal cursors, the structural timeline, the controlled clock and queue, and a complete
synthetic SQLite database under one content-derived integrity hash. `The Long Afternoon` can stop before its
two scheduled inspections, serialize through JSON, restore into a fresh database, and finish with exactly the
same structural result as an uninterrupted run. A damaged envelope, actor substitution, or non-empty target is
refused before database replacement.

Private resident and model state remain under participant custody. The combined envelope carries only an
external artifact's ID, format, version, digest, and byte length; it does not embed private prose. The current
scripted and mechanical participants correctly bind `none`. This is a SQLite-only synthetic restore, not a
portable production database backup and not yet a real reference-resident resume. Its content hash detects
damage and inconsistent substitution, but it does not authenticate an untrusted checkpoint. Next, add the
smallest gym participant adapter that supplies and restores the existing private resident checkpoint through
this binding, verifies the external artifact bytes, and keeps the trust source explicit. Do not add checkpoint
forks, model calls, or training records until that complete adapter path is replayable.

### Scenario coverage map — July 21, 2026

Gym coverage now has two explicit scales. Trustworthiness scenarios test that the apparatus tells the truth:
production-rule parity, authorization, exact-place delivery, delayed work, stop/resume, correspondence, access,
custody, travel, stale-decision rejection, and fault recovery. They stay small and inspectable. The first five
have partial or complete narrow proofs; access/custody, travel, scenario-level stale decisions, and fault
injection still need gym episodes.

Capability and training scenarios come later. They vary attention and timing, conversation, solitude and
learning, plans, relationships, material life, place and travel, uncertain knowledge, long-term change, and
participant/model families. Each family needs generated variation, repeated trials, and held-out cities,
wording, ordering, and seeds. One attractive transcript never counts as coverage. The maintained matrix and
current status live in `docs/reference/resident-gym.md`.

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
