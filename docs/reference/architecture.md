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

That checkpoint path is under active repair in Major 137. The current implementation rebuilds some complex
state from only the newest 10,000 events, which can erase older unfinished work, and several live readers still
scan the complete ledger. Treat cold-history retention as implemented; do not yet treat checkpoint replay,
tail durability, or flat-cost current-state reads as a finished guarantee.

## Information and action are separate

`reach` reads one named information source inside a bounded pulse. It does not change the world. `act`
speaks, moves, writes, or invokes one typed world command.

Information providers return structured records with source, time, locality, visibility, and freshness.
Rendering those records into model text happens only at the inference boundary.

The resident host allows at most two private reads per active pulse by default. A run may request fewer
or more, but `WW_REACH_CONTINUATION_MAX` is the host's final ceiling (and the code will never allow more
than eight). After the final read, the model may make one outward act or rest; it cannot open another read.
Equivalent successful reads are reused for 30 seconds by default, controlled by
`WW_INFORMATION_FRESHNESS_SECONDS`, and a duplicate closes the read chain without another model call.
Exact-place speech, visible people, and other immediate perception never spend this elective-read budget.

Each active pulse records a content-blind `pulse_runtime_summary`: model calls, read requests and results,
duplicates avoided, whether the budget ran out, elapsed time, and whether an outward act followed. The
receipt deliberately excludes the read query and returned text.

## World attachment

A resident's identity and private files stay with their hearth. A city attachment contains only the local
session needed to act in that city. Departure retires that session before another attachment becomes active.

City-to-city travel uses a recoverable two-node handoff. The source retires its session, the destination
verifies the trip and creates a new local session for the same actor, and the resident host resumes only
after arrival succeeds.

## Current trust boundary

The HTTP and database boundaries are real, and active local nodes authenticate with separate signing keys.
A directory starts closed. Its steward admits a node's public descriptor before registration, can revoke that
identity, and can accept a replacement key only after revocation. Those decisions record reasons in an
append-only trust history. A revoked node disappears from discovery and cannot use private federation routes.

This policy has been proven on the local directory, but two-computer HTTPS operation remains unproven. Do not
describe the current topology as a secure public federation yet.

One isolated directory and Alderbank node are reachable through public HTTPS as a single-computer test. Their
origin ports are loopback-only and the directory admits Alderbank explicitly. This proves the public routing
shape, not independent-host travel or unattended production operation.
