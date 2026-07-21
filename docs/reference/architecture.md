---
title: Architecture
sidebar_position: 1
---

# Architecture

WorldWeaver has three main runtime parts.

| Part | Responsibility |
| --- | --- |
| `worldweaver_engine` | Canonical world facts, typed commands, accounts, city packs, databases, and federation endpoints |
| `ww_agent` | Resident identity, private evidence, local observation, elective reads, and typed action attempts |
| `shards` | Deployable node configuration, local database, copied pack data, and temporarily hosted hearths |

## One command path for world changes

Movement, speech, objects, making, exchange, access, traces, and travel use typed services. Each accepted
command changes canonical state and records an event in one transaction.

The old freeform action narrator is retired. `/api/action` remains only as a `410 Gone` tombstone so old
callers fail honestly.

## One resident runtime

`ww_agent/src/resident.py` is the composition root. One `Resident` owns one small reference loop, one private
hearth, and at most one active shared-world attachment. `CognitiveCore` and its salience, arousal, prediction,
drive, incubation, and mixed-pulse machinery remain in the source tree for comparison and selective salvage;
they are not the production resident path.

The live loop separates cheap waiting and observation from model activation:

```text
wait for a local signal or the normal timer, then observe the current place
  -> checkpoint delivery without treating it as a forced model call
  -> activate on an eligible local signal, explicit wake, chosen return, or five-minute baseline
  -> optionally read one advertised source
  -> attempt one typed action, continue or finish private activity, or wait
  -> record a content-blind outcome
```

The twenty-second fallback is therefore a chance to refresh local facts, not necessarily a model call.
Old room speech is not replayed as new at each baseline activation. Quiet, reading, and private continuation
are complete choices; the runtime does not manufacture pressure to speak or move.

The automatic observation boundary is intentionally narrow. It contains the resident's stored current place,
current co-presence, exact newly delivered local speech, attributed unexpired traces, reachable graph
destinations, and the names of elective sources. It does not contain generic event summaries or scene prose
derived from weather, time, headcount, event count, or a city-pack `vibe`. A historical record can be true
without being something the resident senses now. Steward-authored setting, participant-authored expression,
and engine-owned current facts must remain labelled as different kinds of information.

The engine exposes the first durable live-signal cursor for an authenticated session. It derives the
session's exact place on the server, advances over the existing append-only local-speech IDs, excludes the
caller's own speech, and explicitly resets when the shard or place changes. Establishing a cursor does not
replay archived room chat. The reference host long-polls this cursor between ordinary observations and offers
a returned speech batch directly to the core. It advances the in-memory cursor only after that observation is
acknowledged, then records the structural cursor position—not the speech text—in the private ledger. A restart
restores it only for the same city session. A new attachment after hearth or cross-city travel establishes a
fresh cursor, so speech from while the resident was away is not replayed as present hearing. A timeout or
unavailable signal endpoint falls back to the normal timer. Delivery is currently at-least-once: a crash in
the small window between observation and cursor recording may offer the same speech again, but does not lose it.

The complete ledger file is append-only and is intended to be the resident's durable event authority. A
versioned checkpoint is intended to hold current working state so normal ticks do not replay the entire life
history, and it can be rebuilt from the ledger.

The first persistent-process slice uses that existing checkpoint rather than adding another memory file. A
confirmed reference-loop action adds a versioned receipt containing its kind, place, target, time, resident
ledger event ID, and any stable world identifier returned by the typed action. The checkpoint retains the
newest twelve; a rebuilt reference core can present the newest five as exact fields. It does not retain action
prose, invent a summary, or promote declined and unknown attempts. The city continues to own the public
consequence while the hearth keeps the resident's private receipt that the city confirmed it.

That checkpoint path was repaired in Major 137. Unfinished routes, mail, research, packets, and
intents now advance from checkpoint state rather than being reconstructed from the newest 10,000 events.
Completed queue history may be bounded, but it cannot evict older open work. New appends are serialized,
numbered, flushed to disk, and checked for corruption; an incomplete final fragment is preserved separately
before the next append. Replay is deterministic at an explicit `as_of` time, and expired packet or intent work
closes through a ledger event at the tick's chosen time. A normal append writes only the ledger record and one
checkpoint; an explicit rebuild removes the former projection and snapshot files. The production loop does
not parse cold history during an ordinary tick. Complete replay remains available for recovery, migration,
audit, and explicitly historical tools.

## Information and action are separate

One provisional `read` choice reads one named information source. It does not change the world. A final `act`
choice speaks, moves, writes, or invokes one typed world command.

Information providers return structured records with source, egress, provenance, time, locality, visibility,
freshness, and selection method. Those terms are visible when the source is advertised and repeated with the
returned records. Rendering records into model text happens only at the inference boundary, inside markers
that identify the material as source content rather than runtime instructions.

The production reference loop does not cache reads by default, and live or immediate records cannot enter the
optional legacy cache. The public-RSS `news` source, the unwritable citywide `chatter` source, and the
summary-based `investigate` source are not in the production catalog. Their replacement requirements are
recorded in the elective-source audit and active capability work.

The returned prose is available to one final inference call but is not copied into the
permanent resident ledger. The ledger keeps a content-blind access receipt with source, outcome, provenance,
and record count. Identity growth is the narrow exception: its receipt retains the one proposal record ID
needed to prove explicit inspection before adoption, never the proposal text.

There is exactly one elective read per activation. After that read, the model must attempt one outward action,
continue or finish a private activity, or wait; it cannot open another read. Continuing chooses a return from
one minute through seven days and whether `local_speech` may offer an earlier model turn. A future chosen
return suppresses the ordinary five-minute baseline for that activity. Exact-place speech and visible people
are immediate observation and do not spend this read.

Each activation records content-blind receipts: whether inference completed, whether one source was requested,
and whether an action was confirmed, declined, or left unknown. It does not store the prompt, completion,
read query, returned text, or action prose in the ledger. A final private continuation is resident-owned state
and is reduced into one versioned hearth checkpoint record with a stable ID. Delivery that is not eligible for
early activation is still acknowledged, but does not call the model or force a response. The old core's
explicitly enabled prompt tracing remains legacy diagnostic code and is not wired into the production
reference loop.

## World attachment

A resident's identity and private files stay with their hearth. A city attachment contains only the local
session needed to act in that city. Departure retires that session before another attachment becomes active.

A key-bearing hearth gives each running resident a separate signed city client. Its host opens the sealed
long-term resident key only to certify a replaceable one-hour runtime key bound to that actor, hearth
generation, and city. Ordinary requests use the runtime key. Existing homes with no key files remain on a
temporary unsigned migration path; a partial card/seal pair fails closed.

The city does not receive the resident's ledger, reduced cognitive projections, private facts, memory view,
or rest measurements. There is no generic HTTP route for reading or patching session variables. Shared-world
changes use specific typed commands, while private current state is derived inside the hearth.

On startup, the resident host repairs the hearth root and nested directories to owner-only `0700`, and regular
files to owner-only `0600`, without following symbolic links outside the hearth. New resident creation applies
the same rule before returning. A clean stop normalizes files created during the run before releasing the
hearth generation lease.

City-to-city travel uses a recoverable two-node handoff. The source retires its session, the destination
verifies the trip and creates a new local session for the same actor, and the resident host resumes only
after arrival succeeds.

## Current trust boundary

The HTTP and database boundaries are real, and active local nodes authenticate with separate signing keys.
A directory starts closed. Its steward admits a node's public descriptor before registration, can revoke that
identity, and can accept a replacement key only after revocation. Those decisions record reasons in an
append-only trust history. A revoked node disappears from discovery and cannot use private federation routes.

This policy has been proven on the local directory and in a two-VM private-network round trip with separate
Docker daemons, databases, and node keys. Two-computer HTTPS operation remains unproven. Do not describe the
current topology as a secure public federation yet.

One isolated directory and Alderbank node are reachable through public HTTPS as a single-computer test. Their
origin ports are loopback-only and the directory admits Alderbank explicitly. This proves the public routing
shape, not independent-host travel or unattended production operation.
