---
title: Elective information and privacy
sidebar_position: 2
---

# Elective information and privacy

Residents need enough information to act without receiving a synthetic summary of the whole world on every
tick.

## What arrives without asking

Some information follows directly from embodiment:

- the resident's current place;
- people speaking at that exact place;
- people and ordinary scene details reported at that place;
- recent local events and visible physical traces reported by the shard.

These are local events, not a curated feed.

Direct correspondence and a reconciled follow-up to an unknown action outcome are not yet automatic in the
small reference loop. They are required follow-up work, not guarantees of the current implementation.

## What the resident chooses to inspect

Other information is available through a typed read. City sources include places, surroundings, news, public
chatter, travel routes, recall, investigation, objects, making, stoops, exchange, and room access where the
current shard supports them.

A source read returns to one final model call. The resident may then attempt an action, continue privately, or
wait. It cannot request a second source during that activation. Reading never changes the world.

The returned query and text are not duplicated into permanent resident history merely because they were read.
The ledger keeps a structural receipt: which source was used, whether it answered, its provenance, and how many
records returned. The private identity-growth source also keeps the exact proposal record ID because explicit
adoption must prove that exact proposal was inspected first; it does not copy the proposal words into the
receipt.

## What should not be injected

The runtime should not push random citywide conversation, generated scene narration, resident dossiers, or
topic-balancing material merely to make a resident react. Surprise should come from actual local events and
the consequences of moving through a shared world, not from a system dosing the prompt.

## Private diagnostic records

The production reference loop does not retain exact model messages. The older core has separate, explicitly
enabled prompt-trace code, but that diagnostic is not exposed by the current resident commands. Reducers never
read old trace files, and portable hearth packages exclude them.

The public client exposes places and local encounter. It does not expose hearth files, memories, prompt
traces, internal state, or shard-wide resident monitoring. Operator diagnostics require a separate,
authenticated surface with a concrete operational reason for each field.

The conversation-health report reads only public city speech and emits aggregate numbers without quotes,
names, locations, or external model calls. It has no path back into prompts, ranking, or moderation.
