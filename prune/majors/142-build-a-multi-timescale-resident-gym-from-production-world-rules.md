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
portable production database backup. Its content hash detects damage and inconsistent substitution, but it
does not authenticate an untrusted checkpoint.

The private artifact half is now replayable across a real process boundary. It reuses the deterministic portable
hearth package: the engine stores only format, ID, byte count, and digest, while a child agent process verifies
the bytes, imports into staging, rebuilds the derived checkpoint from the private ledger, and checks the exact
actor, hearth generation, attachment, city session, adapter, and model before installation. Tests reject changed
bytes and process substitution without leaving a partial home. A combined test stops the engine episode and
synthetic resident artifact, restores each in its own package context, and produces the same engine result as
the uninterrupted control. The descriptor and content-safe restore report contain no private activity prose.

The resident half of that instruction now exists. `ReferenceResidentCore.handle_scheduled_return` refuses
wrong or early IDs, consumes a due return before inference, and returns `already_processed` without another
model call after checkpoint rebuild.

### First separate-process activation — July 21, 2026

`The Kept Appointment` now closes the combined handoff. The HTTP scene route and the gym share one factual
scene builder, including current presence, public traces, active sublocations, and the route graph. The builder
accepts an injected clock for controlled runs; the gym does not maintain a second scene rule. The agent's HTTP
client and its transport-free gym adapter likewise share one scene parser.

The engine registers the resident's content-free return in its checkpointed queue, restores the synthetic
hearth package in a separate agent process, advances 48 hours, and offers the due event to the real
`ReferenceResidentCore`. For this plumbing test only, the model adapter always chooses `wait`; the core still
performs its normal observation, durable return consumption, inference, and stale-state recheck. The engine
records only scene counts, lifecycle boundaries, status, choice kind, and model-call count.

The episode deliberately drops the first queue acknowledgement after the resident commits its receipt. After
the engine checkpoint restarts, the same event is offered again. The resident reports `already_processed` with
zero model calls, and only then does the engine acknowledge the event. This proves the destructive edge we
needed before using a real resident: an engine retry cannot spend the same private return twice.

Run the streamed proof with:

```bash
python dev.py gym --episode resident-return
```

### Two-way model participant adapter — July 21, 2026

`The Model Appointment` now runs a disposable model-backed reference resident inside the isolated gym. The
engine owns the synthetic database and the agent owns its synthetic hearth and model client in a separate
process. Its first adapter used a versioned stdio vocabulary of named scene, speech, correspondence, place, and
movement operations. That vocabulary has now been removed: stdio carries generic HTTP bytes from the ordinary
`WorldWeaverClient`, and the parent dispatches them through the actual FastAPI application with its database
dependency bound to the isolated gym database.

The synthetic resident has a real host-sealed identity. The client performs public shard-audience discovery,
issues a short-lived runtime certificate, and signs exact encoded request targets and bodies. The gym explicitly
admits only that disposable public identity, activates its runtime generation, binds it to the synthetic
session, and then relies on the normal resident authorization and replay-nonce path. The structural record
retains only method, path, status, and whether complete proof headers were present; it never stores the
certificate, signature, nonce, request body, or private query.

The child now enters through the normal `Resident` host. Its synthetic home carries a normal active
hearth-generation record, the host takes the exclusive runtime lease, resumes the authorized city session,
reads the node's public experience and city-pack profile, constructs the ordinary city source registry, binds
the process, builds the shared reference core, and records a clean suspension before releasing custody. A
bounded `Resident.run_scheduled_return` entrypoint lets the engine offer one exact idempotent appointment
without substituting the polling loop or bypassing host ownership.

The synthetic node identifies itself as `resident_gym` and publishes an ordinary commons with no optional game
capabilities. The host therefore offers `measure`, `recall`, `places`, and `travel`, while correctly withholding
objects, making, exchange, access, and stoops. The deterministic conformance proof performs an elective
`measure` read and then requests travel home. It proves that unsigned readiness discovery and signed profile,
scene, and `/api/session/leave` requests receive 200 responses through the production routes. The normal host
changes attachment only after that retirement succeeds, binds its private process checkpoint to `hearth`, and
releases custody. A second agent process restarts the same stopped home at a real `LocalWorld`, observes the
hearth at the controlled instant with zero model calls, and proves the city sources were replaced by `growth`,
`measure`, and `recall`. The synthetic database contains no remaining city session for that actor. Private
query, result, prompts, completions, and activity prose do not enter the structural trajectory.

Run a real configured model without starting a live town:

```bash
export WW_INFERENCE_KEY=... WW_INFERENCE_MODEL=google/gemini-3-flash-preview
python dev.py gym --episode resident-model
```

The earlier Tansy activation in Alderbank was a bounded live-town smoke run produced by a misunderstanding of
this next step. It did not exercise the gym adapter and is not evidence for Major 142. Keep it classified as
out-of-scope historical operation, and do not run more live-town residents while model-gym scenario and fault
coverage remain the active work.

### Fidelity consolidation — July 21, 2026

The gym must be a controlled way to run WorldWeaver, not a second WorldWeaver implementation. The first
consolidation slice removes duplicate resident composition: the normal `Resident` host and model gym now call
one builder in `ww_agent/src/resident.py` for `ReferenceResidentCore`, `WorldEffector`, `InformationAccess`,
and `Workshop`. Identity loading, process binding, exclusive hearth custody, and attachment lifecycle remain
host responsibilities and are not smuggled into that builder.

Episode schema version 8 includes a machine-readable fidelity profile. The current model episode truthfully
claims the actual FastAPI routes and production engine services, synthetic SQLite state, shared reference-core
composition under the normal `Resident` host, ordinary `WorldWeaverClient` HTTP carried over generic stdio
bytes, signed runtime-certificate authorization, node-published city sources followed by the actual hearth
registry, controlled world time across the exercised engine and resident semantics, confirmed city retirement,
a real `LocalWorld` restart, portable artifacts, and no federation coverage. The stopped home retains its
host-sealed identity; the exported artifacts
deliberately do not. That is useful evidence but not a full-shard claim.

The bounded departure-failure slice is now complete. Every city-to-hearth attempt writes one private stable
transition ID before the request. The production route atomically persists a retirement receipt bound to the
transition, session, actor, and active runtime generation while deleting the live session. The same signed
generation may replay the exact transition after response loss and receives the original receipt; changed
actors, generations, sessions, or transition IDs are refused.

Four deterministic model-gym cases now fail before request dispatch, before the domain commit, after commit
with response loss, and immediately after the hearth process checkpoint. Each restarts the ordinary resident
host. Across every case the model is called only for the original read and home choice, the departure uses one
transition and one stored receipt, `LocalWorld` is reached once, the final process is suspended at hearth, and
the synthetic city has no remaining presence for the actor. The response-loss case observes the same receipt
on both successful HTTP dispatches. Retirement receipt chronology is included in the controlled-time audit.

The process protocol now fails closed on child death, invalid JSON, unknown message types, duplicate request
IDs, and malformed parent responses, and it reaps the failed child. The transition also passes through an
ephemeral Uvicorn server on IPv4 loopback, where the ordinary `WorldWeaverClient` uses real network HTTP while
the same isolated database, clock, signing, host, core, and attachment owners remain in place.

One real `google/gemini-3-flash-preview` call then ran in that isolated loopback episode. The model chose
`finish` after one inference and remained in Willow Court. The runner now recognizes that as a legitimate
suspended city result with one live city attachment and no retirement receipt; it no longer misclassifies
every non-hearth model choice as interrupted travel. No prompt, completion, or private source prose entered the
trajectory, and no live-town resident ran. Episode schema version 9 records the selected transport and the
attachment fidelity actually achieved.

The next bounded infrastructure slice is a container repeat. Optional constructive-game capabilities and
federation require their own explicit scenarios. Do not grow a parallel list of gym-only world abilities in
the meantime.

The controlled-time HTTP prerequisite is now closed for the routes exercised by the model appointment. Live
requests receive `SystemClock`; the isolated gym overrides the same FastAPI dependency with its controlled
clock. Scene building, sublocation listing and creation, and movement resolution therefore agree at one virtual
instant. The model conformance test compares the direct activation scene with the signed HTTP scene at the
willow bench's deadline, and an API test proves an expired child place disappears from both representations and
cannot be entered through movement. Authorization expiry, nonces, process durations, and model latency remain
real-time concerns.

The persistence half now agrees too. Session bootstrap and movement updates, local speech, canonical world
events, fact validity, and projection updates accept the same explicit world instant. Before producing a model
episode result, the gym audits every exercised row against the trajectory's controlled instants and refuses the
result if any row silently used wall time. Correspondence, traces, polls, grounding, durable objects, making,
exchange, stoop, and access HTTP commands now receive this dependency as well, so future capability scenarios
do not need another time architecture. Federation transfer records remain outside the claim alongside the
federation boundary itself. Security expiry, replay guards, rate limits, cache freshness, process timing, and
model latency deliberately remain real or monotonic.

The resident half now has its matching clock seam. `Resident` and `LocalWorld` default to real UTC, while the
gym child receives the engine appointment's controlled instant. Normal core ticks, hearth grounding, whisper
freshness, hearth scene events, local reads, and voice records use that injected world time. Runtime leases,
process suspension duration, retry sleeps, certificate expiry, nonce validation, and inference latency remain
on their operational clocks.

### Scenario coverage map — July 21, 2026

Gym coverage now has two explicit scales. Trustworthiness scenarios test that the apparatus tells the truth:
production-rule parity, authorization, exact-place delivery, delayed work, stop/resume, correspondence, access,
custody, travel, stale-decision rejection, and fault recovery. They stay small and inspectable. The first five
have partial or complete narrow proofs; access/custody, federated travel, and scenario-level stale decisions
still need gym episodes. The city-to-hearth fault boundary now has request, transaction, response-loss, and
post-checkpoint process coverage.

Capability and training scenarios come later. They vary attention and timing, conversation, solitude and
learning, plans, relationships, material life, place and travel, uncertain knowledge, long-term change, and
participant/model families. Each family needs generated variation, repeated trials, and held-out cities,
wording, ordering, and seeds. One attractive transcript never counts as coverage. The maintained matrix and
current status live in `docs/reference/resident-gym.md`.

The terminal runner streams each structural record as the corresponding production receipt or signal read
returns, while still writing the finished HTML report. This is a real callback at record creation rather than
post-run animation. The model adapter uses that surface for content-safe observation, inference start/finish,
choice, action receipt, retry, and scheduled-return boundaries without exposing private reasoning or hearth
prose.

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
- [x] One episode can combine sub-minute conversation with multi-day scheduled activities without sleeping
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
