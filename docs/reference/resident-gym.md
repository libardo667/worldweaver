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

Each command prints a compact timeline and writes a self-contained visual report under `.runs/gym/`
(`footbridge-hello.html`, `waiting-letter.html`, `long-afternoon.html`, or `kept-appointment.html`). The reports
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
controlled time, checkpoint forks, model adapters, and training data remain later work.

## What the mixed-time episode proves

`The Long Afternoon` starts with ordinary exact-place speech. Mara then creates a real ephemeral sublocation,
the willow bench, with a two-day lifetime. A controlled UTC clock jumps forward 47 hours and the production
lifetime rule still reports the bench active. It jumps two more hours and the same rule reports the bench
expired. The terminal and browser views show exact timestamps and mark those jumps with a sun-and-moon trail.

This is the first explicit clock seam, not the completed time system. The live code continues to use real UTC,
while tests and gym episodes may use a controlled clock that cannot move backward. The episode passes that time
into an existing production rule; it does not patch global time or sleep.

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

## First model-backed control

On July 21, 2026, a new name-only resident named Tansy completed one bounded live activation in Alderbank. The
resident began with no biography, voice samples, model output, or ledger history. Public identity admission,
hearth activation, and read-only preflight were separate steps.

Using `google/gemini-3-flash-preview`, Tansy made two inference calls: one elective read followed by one final
decision. The run used 1,438 prompt tokens and 67 completion tokens and took 6.801 seconds. The public result
was one confirmed move from Alderbank Commons to Commons Bank, with no speech. The runner then retired the city
session and parked Tansy at the hearth.

The review used only structural counters and the public movement receipt. It did not inspect the private query,
source result, prompts, completions, or ledger prose. This single run shows that the live reference path can
support a read followed by a grounded action; it says nothing general about capability or model diversity.

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
| Production-rule parity | Footbridge episode matches an authenticated in-process HTTP replay | Repeat selected paths against a running container |
| Identity and authorization | Anonymous signal access is refused; correspondence uses durable actor IDs | Cover every gym action and resident proof type |
| Exact-place perception | Speech follows location and a durable cursor | Reconnect, cursor gaps, and concurrent arrival/speech ordering |
| Delayed work | Stable scheduled IDs, controlled UTC, explicit acknowledgement, and idempotent private-return retry | Other state-changing handlers and failed-handler retry |
| Stop and resume | A separate reference core refuses a second model call after lost acknowledgement; a bounded live resident returns cleanly to its hearth | Gym-hosted model runs, live scheduled-return wiring, and authenticated portable checkpoints |
| Correspondence | Mail survives a session change and remains pending until acknowledgement | Interruption policy, cross-shard delivery, and failure recovery |
| Access and custody | Production services exist outside the gym | Refusal, making, carrying, giving, exchange, and stoop episodes |
| Travel | Production service exists outside the gym | Recoverable local and federated travel episodes |
| Stale information | Structural version fence exists in the reference resident | Change the world during a gym decision and prove safe reconsideration |
| Fault recovery | Individual service rollback tests exist | Scenario-level database, process, and network fault injection |

The command-line runner exposes these records as a live, flushed stream while retaining the final HTML and JSON
reports. The separate-process return episode emits content-safe observation and activation boundaries, making
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
