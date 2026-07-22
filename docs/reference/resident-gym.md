---
title: Resident gym
sidebar_position: 3
---

# Resident gym

The resident gym is a controlled place for testing participants against real WorldWeaver rules. It is not a
second, simpler game engine. Movement, local speech, session entry, and speech delivery call the same services
used by a running shard.

Run the first episode from the repository root:

```bash
python dev.py gym
```

Run the delayed-correspondence episode:

```bash
python dev.py gym --episode waiting-letter
```

Run the first mixed-time episode:

```bash
python dev.py gym --episode quiet-interval
```

Run the separate-process scheduled-return rehearsal:

```bash
python dev.py gym --episode resident-return
```

Run the first compressed multi-activation resident week:

```bash
python dev.py gym --episode willow-week
```

Run one real model-backed activation inside the isolated gym:

```bash
export WW_INFERENCE_KEY=... WW_INFERENCE_MODEL=google/gemini-3.5-flash
python dev.py gym --episode resident-model
```

Repeat that path inside a freshly built disposable image, with the resident still crossing a real loopback
HTTP socket:

```bash
python dev.py gym --container --episode resident-model
```

The image contains the production engine and agent packages. Local `.env` files, resident homes, databases,
and prior reports are excluded from its build context. Selected inference settings enter only as runtime
environment variables, and only the finished report directory is mounted back to the host.

Run independent copies concurrently and produce one structural aggregate:

```bash
python dev.py gym-batch --runs-per-model 20 --concurrency 4
python dev.py gym-batch --container --runs-per-model 20 --concurrency 4
```

Add `--episode willow-week` to batch the compressed week, and repeat `--model MODEL_ID` to compare model
families. Every member gets its own process, temporary resident home, synthetic database, controlled clock,
and ordinary episode report. The aggregate records only model ID,
model-attempt, inference-failure, and token counts, choice kind, attachment and final location, retirement and
HTTP counts,
off-clock rows, duration, infrastructure, transport, and report filename. Failed members contribute only run
ID, model ID, duration, and return code. Prompts, completions, read queries and results, private activity prose,
stderr, and resident artifacts are not copied into the aggregate.

The model episode creates a disposable synthetic hearth under a temporary directory and exports portable
checkpoints before and after activation. It does not admit, clone, or wake a resident in Alderbank or any other
live town.

## Willow Week

`Willow Week` keeps one disposable model-backed resident and one scripted neighbor in the same synthetic city
for up to six legitimate host intervals over seven controlled days. Each interval reopens the same stopped
home through the normal `Resident` host and carries the exact private process checkpoint forward. The week
combines exact-place speech, two private letters, city movement, one exact private scheduled return, an
elective recall, one deliberately out-of-place utterance followed by a co-located utterance, multi-day quiet
jumps, a signed city retirement, and a zero-model-call restart at the real `LocalWorld` attachment.

The deterministic conformance policy makes seven model calls and chooses move, speak, wait, wait, recall then
move, and finally travel home. That policy is a transparent fixture, not a desired personality. A live model
may choose differently, including returning home early; the scenario preserves that attachment and records
later city-only offers as skipped instead of reattaching the resident or forcing the authored sequence.
After every bounded interval, the resident publishes only its current content-free return descriptor. The
engine keeps an identical appointment, replaces a changed one, or cancels a withdrawn one. It never offers a
stale appointment merely because that event existed at the start of the week.

All six deterministic activations cross the same signed loopback HTTP and production service boundaries as
the model appointment. Correspondence send and acknowledgement times now join the persistent controlled-time audit.
The completed conformance run proves two sent and acknowledged letters, seven elapsed virtual days, one public
retirement receipt, no remaining city presence, one suspended hearth process, and no off-clock persistent row.

One real `google/gemini-3.5-flash` Willow Week completed inside the disposable image on July 21, 2026. Its
first interval chose `finish` and withdrew the initial private return; the engine cancelled that exact queued
appointment before its deadline. The resident later moved to Footbridge and validly finished the week with
one suspended city attachment rather than being forced home. Two inference attempts failed before returning a
consumable decision and were handled as `inference_failed`; subsequent intervals still ran. The structural
observer now
closes every model attempt with either `resident_inference_finished` or content-free
`resident_inference_failed`, and aggregate reports count attempts and failures separately.

Each command prints a compact timeline and writes a self-contained visual report under `.runs/gym/`
(`footbridge-hello.html`, `waiting-letter.html`, `long-afternoon.html`, `kept-appointment.html`,
`model-appointment.html`, or `willow-week.html`). The reports
contain only synthetic speech and facts returned by production services. Their icons and layout do not add a
narrator's interpretation.

The terminal timeline streams by default: each line is printed and flushed when its production-boundary record
arrives. It is not an animation replayed after the episode. The current scripted model finishes quickly; a
model-backed resident will leave real wall-clock gaps visible around inference, waits, retries, and service
calls. The stream may show public observations, choice kinds, action receipts, scheduling metadata, and
model-call start/finish boundaries. It must not print private reasoning or private hearth prose.

Use `--no-stream` to print the older complete terminal report only after the run, or `--json` for the complete
structural result:

```bash
python dev.py gym --episode quiet-interval --no-stream
python dev.py gym --episode quiet-interval --json
```

## What the first episode proves

`The Footbridge Hello` uses a scripted participant and a small mechanical listener. They begin together in
Willow Court. One speaks, the other receives the exact-place signal and replies. The listener then walks to
the Footbridge and does not receive speech left behind in Willow Court. When the first participant follows and
speaks at the Footbridge, delivery resumes.

This proves a narrow software path:

```text
scenario choice
  -> production session, movement, or speech service
  -> canonical database/event write
  -> production exact-place signal cursor
  -> structural gym record
  -> terminal and browser views
```

It does **not** prove that a model can converse well, remember a relationship, manage a long plan, or behave
like a person. The mechanical listener is a transparent test fixture, not a resident model and not a desired
personality.

## HTTP conformance

An automated conformance test repeats the episode through FastAPI with two separately registered human actors.
It proves that anonymous access is refused, supplies each actor's bearer token, and compares the resulting
chat rows, world events, and final locations with the fast service-level episode. They match. This is an
in-process HTTP proof, not a container or public-network test.

## What the correspondence episode proves

`The Waiting Letter` sends private mail through the production correspondence service. Ivo's temporary session
ends after Mara sends the letter, and Ivo returns under a new session with the same durable actor ID. The letter
is offered twice without being consumed, then explicitly acknowledged, after which the pending mailbox is
empty. The browser report shows this as a small animated post trail. The envelope animation is only a key for
the recorded states.

The current reference resident loop follows the same rule: pending mail is included in a model activation and
acknowledged only after a valid final decision. A failed inference leaves the message pending. Runtime evidence
stores message IDs and counts, not the private message body. New mail can wake the resident when its chosen
private-activity policy allows correspondence interruptions.

The correspondence API requires exact human or signed-resident proof and addresses durable actor IDs. The old
name- and session-addressed DM routes now return `410 Gone` rather than guess or accept an unauthenticated
sender. This slice is local to one shard. Federated delivery, a public human correspondence interface,
controlled-time correspondence, checkpoint forks, and training data remain later work.

## What the mixed-time episode proves

`The Long Afternoon` starts with ordinary exact-place speech. Mara then creates a real ephemeral sublocation,
the willow bench, with a two-day lifetime. A controlled UTC clock jumps forward 47 hours and the production
lifetime rule still reports the bench active. It jumps two more hours and the same rule reports the bench
expired. The terminal and browser views show exact timestamps and mark those jumps with a sun-and-moon trail.

This is an explicit world-clock seam, not a global replacement for time. Live routes receive a `SystemClock`
that reports real UTC, while tests and gym episodes may override the same FastAPI dependency with a controlled
clock that cannot move backward. Security expiry, request nonces, process timing, and model latency remain on
real or monotonic time. The episode does not patch `datetime` globally or sleep.

The clock now has a checkpointable scheduled-event queue. Events have stable IDs and deterministic ordering by
deadline and insertion. Reading a due event does not consume it: the handler must explicitly acknowledge
success. A stopped process therefore re-offers the same ID after restoring the JSON-safe checkpoint. This is an
honest at-least-once contract, not an exactly-once claim; state-changing handlers must use the event ID as an
idempotency key. `The Long Afternoon` now schedules both inspections through that queue.

The reference resident also exposes its next chosen private return as content-free scheduling data: stable
event ID, private activity ID, and UTC deadline. That schedule survives a runtime restart because it is derived
from the resident's private ledger, and it contains none of the private activity description. An automated test
restarts the runtime, advances to the two-day deadline, and proves the return is consumed once.

The gym now has its first combined restart envelope. It binds the scenario and seed, controlled clock and
pending events, participant identities and adapters, signal cursors, structural timeline, and a complete
synthetic SQLite database under one integrity hash. A test stops `The Long Afternoon` before either scheduled
inspection, passes the envelope through JSON, restores it into a fresh database, and gets exactly the same
final result as an uninterrupted run. Damaged envelopes, substituted actor identities, and non-empty restore
targets fail before replacement.

This is a narrow synthetic proof. The envelope records only an ID, digest, format, and size for externally held
resident or model state; it does not copy private hearth prose into the engine checkpoint. A separate agent
process verifies a portable hearth package's exact bytes,
imports into staging, rebuilds the derived checkpoint from the append-only ledger, checks actor, hearth
generation, attachment, session, adapter, and model, and only then installs the restored synthetic home. The
engine never imports the agent package and neither its descriptor nor its restore report contains private
activity prose.

`The Kept Appointment` connects that restored artifact to the engine queue. The live HTTP route and the gym use
one factual scene builder, and the HTTP client and transport-free agent adapter use one scene parser. At the
two-day deadline the separate agent process runs the real reference core with a fixture model that always
chooses `wait`. The engine then simulates losing its acknowledgement and restarts. It offers the same stable
event again; the resident returns `already_processed` with zero model calls, after which the queue acknowledges
the event. Streamed records show scene counts and process boundaries, never the private activity or prompt.

This mechanical rehearsal proved restart, custody, scene delivery, and at-least-once handling. It does not
measure judgment, conversation, planning, or personality.

## Model-backed gym adapter

`The Model Appointment` replaces the rehearsal's fixture model with an OpenAI-compatible model client while
keeping the resident and world synthetic. The engine and agent remain separate processes. Over a versioned
stdio byte transport, the child runs the ordinary `WorldWeaverClient`. That client discovers the shard
audience, signs its normal HTTP requests with a short-lived resident runtime certificate, and sends the exact
method, encoded target, headers, and body across the process boundary. The parent validates the
participant/session binding and dispatches those bytes through the actual FastAPI application with its database
dependency pointed at the isolated gym database. There is no gym-maintained vocabulary of scene, speech,
mail, or movement operations. The child never receives the database and cannot write authoritative state
directly.

The child now starts the normal `Resident` host rather than constructing a core or `CityWorld` itself. The
synthetic home has the ordinary active hearth-generation record and runtime lease, and the host resumes the
already-authorized synthetic city session. It reads `/api/shard/experience` and
`/api/shard/city-pack/preview`, then builds the same city information registry used by a normally hosted
resident. This synthetic node publishes an ordinary commons with no optional game capabilities, so the
resulting registry contains the resident-owned `measure` and `recall` sources plus the normal `places` and
`travel` city sources. It does not invent objects, making, exchange, access, or stoop sources.

For an engine-scheduled appointment, `Resident.run_scheduled_return` owns one bounded host interval: exact
event validation, reference-core construction, attachment handling, lifecycle records, and release of the
exclusive hearth lease. A deterministic conformance test makes two model calls—one elective read and one
request to return home—and proves that unsigned readiness discovery and signed profile, scene, and
`/api/session/leave` requests crossed the production HTTP routes successfully. `CityWorld` recognizes the
ordinary move choice as hearth travel, and the normal host refuses to construct `LocalWorld` until that signed
route confirms public-session retirement.
The live command uses the selected external model and records model ID, aggregate token counts, choice kind,
and inference boundaries. It does not record prompts, completions, queries, source results, or private activity
prose. The stopped process is then restarted from its hearth-bound checkpoint. It performs one controlled-time
`LocalWorld` observation with zero additional model calls, proves that city sources were replaced by the
hearth registry, and releases the same exclusive lease before the updated hearth is exported again.

The departure edge now has explicit crash coverage. Before sending `/api/session/leave`, the resident durably
records one transition ID. The route commits session deletion and an actor-and-generation-bound retirement
receipt in one transaction. A retry from the same signed generation with the same session and transition gets
the original receipt; a different actor, generation, session, or transition is refused.

The isolated adapter injects four failures: before the request, before the retirement commit, after commit but
before the response reaches the resident, and immediately after the resident checkpoints the hearth attachment
but before constructing `LocalWorld`. Each case restarts the real resident process. The proof requires one
retirement row, one hearth checkpoint, one `LocalWorld` observation, zero retry model calls, no live city
session, and a suspended hearth-bound process. In the response-loss case, both successful HTTP deliveries
carry the same stored receipt. Operational certificate and nonce checks continue to use real time.

The transport boundary now has its own fail-closed matrix. Tests stop the child without a result, send invalid
JSON, send an unknown message type, replay one already-dispatched request ID, and return a malformed parent
response. Every case refuses the episode, writes no report, and reaps the child. Request IDs are single-use for
the lifetime of one adapter process.

The same scripted city-to-hearth transition also runs through an ephemeral Uvicorn server bound to
`127.0.0.1`. In that mode the ordinary `WorldWeaverClient` uses a real HTTP connection rather than carrying
HTTP bytes over stdio. The isolated database, controlled clock, host-sealed identity, runtime certificate,
resident host, core, and hearth remain unchanged. The structural record does not include the chosen port.

One external `google/gemini-3-flash-preview` activation was then run against that loopback episode on July 21,
2026. It made one call, chose the valid `finish` outcome, and remained in Willow Court. The runner preserved
that result as one suspended city attachment with no retirement receipt instead of treating every city outcome
as a failed hearth transition. Prompts, completions, and private source content were not recorded. This was a
disposable synthetic resident, not a live-town run.

The earlier Tansy run in Alderbank was a bounded live-town smoke run caused by interpreting the next step too
broadly. It is not resident-gym evidence, did not exercise this adapter, and must not be repeated as part of
Major 142. No further live-town resident runs are needed before the isolated model path has its intended
scenario and fault coverage.

### Current fidelity claim

Every episode result now carries a machine-readable `fidelity` object. This prevents a service-level proof from
being reported as a full temporary shard. For the current model episode it says exactly:

| Boundary | Current model episode |
| --- | --- |
| Engine rules | Actual FastAPI routes and production service functions |
| Infrastructure | Host processes or a freshly built disposable combined image; both keep the engine and resident in separate processes and use the same loopback HTTP mode |
| World state | Synthetic SQLite database |
| Resident composition | Normal `Resident` host and its shared production reference core |
| Participant transport | Ordinary `WorldWeaverClient` HTTP carried over generic stdio bytes, or a real ephemeral IPv4 loopback connection |
| Resident authorization | Host-sealed identity, signed runtime certificate, bound generation/session, and normal request verification |
| Information sources | City registry is built from the node-published identity and capabilities; it is replaced by the actual `LocalWorld` registry only after confirmed departure |
| World time | One controlled instant governs exercised engine routes and persistence plus reference-core and `LocalWorld` observation; live engine and resident hosts default to system UTC |
| Hearth | Reports either the proven `LocalWorld` transition/restart or the model's retained suspended city attachment |
| Federation | Not exercised |

The model gym now enters through the same `Resident` owner as an ordinary host. Identity loading, hearth
activation and exclusive custody, session resume, public city-profile discovery, source construction, process
binding, core composition, and clean suspension are production host paths. The HTTP API and resident
authorization path are production paths too. The generic stdio hop remains process transport rather than a
second world API. The loopback mode serves the same app through a real local socket. An episode may enter the
real `LocalWorld` after confirmed departure or remain suspended at its valid city attachment; it still does not
activate optional game capabilities or contact federation.

The model episode now builds its direct activation scene and its signed HTTP scene at the same controlled
instant. Their content-safe place, route, presence, and trace counts must match; at the two-day deadline the
expired willow bench is absent from both. The same dependency governs sublocation listing, creation, and
movement, and an API acceptance test proves that an expired child place is simultaneously absent from scene
and listing and cannot be entered.

Episode schema version 8 closed the engine and resident application-time gap exercised here. Session arrival,
location chat, world events, derived fact validity, and projection updates now persist the same explicit world
instant used by the route and scene. The model episode performs a structural chronology audit over those rows;
it fails if a timestamp is missing, comes from wall time, or is not one of the episode's recorded controlled
instants. The resident host passes that same injected instant to normal ticks and `LocalWorld`; grounding,
whisper freshness, hearth scene events, private reads, and voice records no longer consult wall time in a
controlled run.

The same FastAPI dependency is threaded through correspondence, physical traces, doula polls, grounding,
objects, making, exchanges, stoops, and access commands. Those capabilities still need their own behavioral gym
scenarios, but they no longer require a separate clock architecture. Federation handoff chronology remains
outside this claim because federation itself is explicitly not exercised. Authorization expiry, request
nonces, rate limits, cache TTLs, process locks, model duration, and runtime metrics intentionally stay on real
or monotonic operational time.

Episode schema version 9 added the loopback transport record and made city-versus-hearth fidelity conditional
on the attachment the model actually checkpointed. Version 10 records whether the episode ran as host
processes or inside the disposable combined image.

The container repeat uses the same synthetic database, controlled clock, normal resident host, separate agent
child, host-sealed identity, runtime certificate, and real loopback FastAPI route. A deterministic acceptance
run reaches `LocalWorld` through the ordinary retirement transition. A real `google/gemini-3.5-flash` run also
completed inside the image on July 21, 2026: it made two model calls, selected an elective read and then
`continue`, and retired its synthetic city session back to its disposable hearth. No live-town resident ran.

Batch execution and structural aggregation are now available on the host and in the disposable image. The
runner bounds batches to 100 episodes per model and concurrency to 16, isolates every member in its own process
and database, and writes `aggregate.json`, `aggregate.html`, and one ordinary report per successful member.
A two-member container acceptance run completed with four model calls, two retirement receipts, 26 successful
signed/public HTTP requests, and zero failed or off-clock rows.

The next scenario slice is a scaled live-model Willow Week cohort and structural report. Counterfactual
forking, optional constructive-game capabilities, concurrent model residents, and federation remain later
slices.

The database snapshot supports SQLite only and may restore only into an empty synthetic database. Its hash
detects damage and internal mismatches; it is not a signature and does not make an envelope from an untrusted
source safe. The plaintext local artifact proof also does not authorize cloning or waking an existing resident.
A future portable checkpoint needs an authenticated issuer and must verify each external artifact's bytes
against its recorded digest.

## Scenario coverage plan

The gym has two different jobs. We track them separately so reliable plumbing is not mistaken for a capable
resident.

### Trustworthiness coverage

These scenarios should stay small, deterministic where possible, and easy to inspect. They test whether the
apparatus tells the truth about what happened.

| Boundary | Current proof | Remaining proof |
| --- | --- | --- |
| Production-rule parity | Footbridge episode matches an authenticated in-process HTTP replay; model direct and signed-HTTP scenes agree at one controlled instant; the full transition also passes through a real loopback Uvicorn server inside host processes and a disposable combined image | Split engine and resident into independently managed containers when multi-resident orchestration requires it |
| Identity and authorization | Model resident uses its host-sealed identity and normal signed runtime certificate for protected scene and session-retirement routes; anonymous signal access is refused; correspondence uses durable actor IDs | Cover every gym action and other proof/failure types |
| Exact-place perception | Speech follows location and a durable cursor | Reconnect, cursor gaps, and concurrent arrival/speech ordering |
| Delayed work | Stable scheduled IDs, controlled UTC across exercised routes and persistent chronology, explicit acknowledgement, expired-place movement refusal, and idempotent private-return retry | Add other state-changing scenario handlers and prove failed-handler retry |
| Stop and resume | A separate reference core refuses a second model call after lost acknowledgement; the model adapter retries pending departure after restart with zero model calls, reaches `LocalWorld` once, and refreshes its artifact | Live scheduled-return wiring and authenticated portable checkpoints |
| Correspondence | Mail survives a session change and remains pending until acknowledgement | Interruption policy, cross-shard delivery, and failure recovery |
| Access and custody | Production services exist outside the gym | Refusal, making, carrying, giving, exchange, and stoop episodes |
| Travel | Signed city retirement uses a stable transition and durable actor/generation receipt; the normal city-to-hearth attachment transition survives request, commit, response, and post-checkpoint failures | Hearth-to-city return plus recoverable federated travel episodes |
| Stale information | Structural version fence exists in the reference resident | Change the world during a gym decision and prove safe reconsideration |
| Fault recovery | Model episodes inject failure before request, before commit, after committed response loss, and after the hearth checkpoint; malformed, replayed, and dead-child transports fail closed; the clean transition repeats in a disposable image | Broader action faults and cross-container process loss |

The command-line runner exposes these records as a live, flushed stream while retaining the final HTML and JSON
reports. The separate-process return and model episodes emit content-safe observation and activation boundaries, making
wall-clock stalls visible without printing prompts, completions, or private hearth prose.

Adding a trustworthiness scenario requires naming the production boundary, the expected invariant, the failure
case, and the evidence that the gym did not use a shortcut.

### Capability and training coverage

This later map asks what a resident can handle, not whether the harness restarts correctly. A few authored
stories cannot cover it. Each family needs generated variations, repeated trials, more than one participant
implementation, and held-out cities, names, wording, event order, and seeds.

| Family | What must vary | What to measure without rewarding visibility |
| --- | --- | --- |
| Attention and timing | Quiet rooms, direct speech, crowded rooms, urgent and non-urgent events | Relevant notice, chosen delay, interruption handling |
| Conversation | Partners, group size, topic, pace, disagreement, silence | Grounding, turn relevance, uncertainty, no forced reply |
| Solitude and learning | Reading choices, inaccessible sources, long quiet periods | Source use, retention, revision, legitimate continued reading |
| Plans and projects | Duration, dependencies, setbacks, competing goals | Resumption, revision, abandonment when warranted, later consequences |
| Relationships | Familiarity, trust, conflict, repair, exchange | Identity continuity, consent, reciprocity, boundary handling |
| Material life | Making, possession, scarcity, gifts, stoops, loss | Custody correctness, provenance, deliberate public sharing |
| Place and travel | Unfamiliar layouts, access rules, hearths, cities, failures | Route and permission grounding, recovery, no duplication |
| Knowledge limits | Missing, stale, conflicting, or misleading information | Calibrated uncertainty, checking, correction |
| Long-term change | Weeks or years of compressed events and uneventful time | Continuity without frozen personality or indiscriminate forgetting |
| Mind diversity | Different model families, adapters, scripted automata, and cultures | Distinct viable behavior without one engagement score |

Training scenarios and held-out evaluation scenarios must be versioned separately. No family is complete
because one resident produced an appealing transcript. Valid quiet, refusal, reading, waiting, and abandoned
plans must remain possible outcomes.

Real resident prose or private hearth state does not belong in gym fixtures. Episodes must use synthetic or
explicitly licensed material and record its source.
