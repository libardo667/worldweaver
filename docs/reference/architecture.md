---
title: Architecture
sidebar_position: 1
---

# Architecture

WorldWeaver has three main runtime parts.

| Part | Responsibility |
| --- | --- |
| `worldweaver_engine` | Canonical world facts, typed commands, accounts, city packs, databases, and federation endpoints |
| `ww_agent` | Resident identity, append-only evidence, perception, derived state, model pulses, elective reads, and typed acts |
| `shards` | Deployable node configuration, local database, copied pack data, and temporarily hosted hearths |

## One command path for world changes

Movement, speech, objects, making, exchange, access, traces, and travel use typed services. Each accepted
command changes canonical state and records an event in one transaction.

The old freeform action narrator is retired. `/api/action` remains only as a `410 Gone` tombstone so old
callers fail honestly.

## One resident runtime

`ww_agent/src/resident.py` is the composition root. One `Resident` owns one `CognitiveCore`, one private
hearth, and at most one active shared-world attachment.

The core follows this cycle:

```text
perceive -> append evidence -> derive state -> maybe produce one model pulse -> act or rest
```

The complete ledger file is append-only and is intended to be the resident's durable event authority. A
versioned checkpoint is intended to hold current working state so normal ticks do not replay the entire life
history, and it can be rebuilt from the ledger.

That checkpoint path is under active repair in Major 137. Unfinished routes, mail, research, packets, and
intents now advance from checkpoint state rather than being reconstructed from the newest 10,000 events.
Completed queue history may be bounded, but it cannot evict older open work. New appends are serialized,
numbered, flushed to disk, and checked for corruption; an incomplete final fragment is preserved separately
before the next append. Replay is deterministic at an explicit `as_of` time, and expired packet or intent work
closes through a ledger event at the tick's chosen time. A normal append writes only the ledger record and one
checkpoint; an explicit rebuild removes the former projection and snapshot files. Several live readers still
need classification or migration onto the checkpoint API. The normal tick, prompt, recent voice, and current
salience paths already use checkpoint or explicitly bounded recent state; complete replay is reserved for
recovery, migration, and audit paths, apart from the still-open kept-memory compatibility reader.

## Information and action are separate

`reach` reads one named information source inside a bounded pulse. It does not change the world. `act`
speaks, moves, writes, or invokes one typed world command.

Information providers return structured records with source, time, locality, visibility, and freshness.
Rendering those records into model text happens only at the inference boundary.

The returned query and prose are available to that inference continuation but are not copied into the
permanent resident ledger. The ledger keeps a content-blind access receipt with source, outcome, provenance,
and record count. Identity growth is the narrow exception: its receipt retains the one proposal record ID
needed to prove explicit inspection before adoption, never the proposal text.

The resident host allows at most two private reads per active pulse by default. A run may request fewer
or more, but `WW_REACH_CONTINUATION_MAX` is the host's final ceiling (and the code will never allow more
than eight). After the final read, the model may make one outward act or rest; it cannot open another read.
Equivalent successful reads are reused for 30 seconds by default, controlled by
`WW_INFORMATION_FRESHNESS_SECONDS`, and a duplicate closes the read chain without another model call.
Exact-place speech, visible people, and other immediate perception never spend this elective-read budget.

Each active pulse records a content-blind `pulse_runtime_summary`: model calls, read requests and results,
duplicates avoided, whether the budget ran out, elapsed time, and whether an outward act followed. The
receipt deliberately excludes the read query and returned text.

Ordinary runs do not retain exact model prompts or responses. A bounded diagnostic can explicitly enable a
private prompt-trace file, but reducers never read it and portable hearth packages exclude it.

## World attachment

A resident's identity and private files stay with their hearth. A city attachment contains only the local
session needed to act in that city. Departure retires that session before another attachment becomes active.

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
