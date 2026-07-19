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

The complete ledger is append-only. A versioned checkpoint stores a bounded working projection so normal
ticks do not replay the entire life history. The checkpoint can be rebuilt from the ledger.

## Information and action are separate

`reach` reads one named information source inside a bounded pulse. It does not change the world. `act`
speaks, moves, writes, or invokes one typed world command.

Information providers return structured records with source, time, locality, visibility, and freshness.
Rendering those records into model text happens only at the inference boundary.

## World attachment

A resident's identity and private files stay with their hearth. A city attachment contains only the local
session needed to act in that city. Departure retires that session before another attachment becomes active.

City-to-city travel uses a recoverable two-node handoff. The source retires its session, the destination
verifies the trip and creates a new local session for the same actor, and the resident host resumes only
after arrival succeeds.

## Current trust boundary

The HTTP and database boundaries are real, but the public federation trust model is unfinished. Local nodes
still share one federation token. Do not describe the current topology as a secure open federation.
