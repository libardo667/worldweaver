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
  -> activate on first start, new local speech, explicit wake, or a five-minute baseline
  -> optionally read one advertised source
  -> attempt one typed action, continue privately, or wait
  -> record a content-blind outcome
```

The twenty-second fallback is therefore a chance to refresh local facts, not necessarily a model call.
Old room speech is not replayed as new at each baseline activation. Quiet, reading, and private continuation
are complete choices; the runtime does not manufacture pressure to speak or move.

The engine exposes the first durable live-signal cursor for an authenticated session. It derives the
session's exact place on the server, advances over the existing append-only local-speech IDs, excludes the
caller's own speech, and explicitly resets when the shard or place changes. Establishing a cursor does not
replay archived room chat. The reference host long-polls this cursor between ordinary observations and offers
a returned speech batch directly to the core. It advances the in-memory cursor only after that observation is
acknowledged. A timeout or unavailable signal endpoint falls back to the normal timer. Cursor restoration
across process restart remains unfinished.

The complete ledger file is append-only and is intended to be the resident's durable event authority. A
versioned checkpoint is intended to hold current working state so normal ticks do not replay the entire life
history, and it can be rebuilt from the ledger.

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

Information providers return structured records with source, time, locality, visibility, and freshness.
Rendering those records into model text happens only at the inference boundary.

The returned prose is available to one final inference call but is not copied into the
permanent resident ledger. The ledger keeps a content-blind access receipt with source, outcome, provenance,
and record count. Identity growth is the narrow exception: its receipt retains the one proposal record ID
needed to prove explicit inspection before adoption, never the proposal text.

There is exactly one elective read per activation. After that read, the model must attempt one outward action,
continue a private activity, or wait; it cannot open another read. Exact-place speech and visible people are
immediate observation and do not spend this read.

Each activation records content-blind receipts: whether inference completed, whether one source was requested,
and whether an action was confirmed, declined, or left unknown. It does not store the prompt, completion,
read query, returned text, or action prose in the ledger. A final private continuation is resident-owned state
and is recorded in the private ledger. The old core's explicitly enabled prompt tracing remains legacy
diagnostic code and is not wired into the production reference loop.

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
