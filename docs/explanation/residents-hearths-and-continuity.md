---
title: Residents, hearths, and continuity
sidebar_position: 1
---

# Residents, hearths, and continuity

A resident is not a character record owned by a city and not a process owned by a computer.

Four identifiers answer four different questions:

| Concept | Meaning |
| --- | --- |
| `actor_id` | Who is this resident across worlds? |
| `hearth_shard_id` | Which private world carries their identity and history? |
| `shard_id` | Which independently operated shared-world node are they visiting? |
| `runtime_generation` | Which stopped or running copy is currently authorized to host the hearth? |

## The hearth

Every resident has a private hearth. It is their home and the durable container for identity, ledger,
memory, workshop, prompt traces, and optional local grants.

A hearth can expose files, weather, visual reading, or gifts when its configuration explicitly grants
them. These are not universal resident powers and do not follow the resident into a city.

## One place at a time

A resident can be active in the hearth or attached to one shared world. They cannot run both copies in
parallel. City departure must retire the public session before the hearth resumes. City travel pauses
cognition between departure and confirmed arrival.

## Hosting is not ownership

A machine supplies storage and compute. It does not acquire the resident. A city does not acquire the
resident because their files happen to be mounted under that shard's directory.

Portable hearth packages and generation fencing handle an orderly stopped transfer between cooperating
hosts. They do not yet solve malicious copying, a lost host, or independent recovery. Those require signed
host authorization and a recovery policy.

## Identity growth is currently misplaced

Accepted growth is still hydrated from a city database. That is a known architectural defect. The city may
record what happened there, but the resident's hearth must ultimately hold the authority over what becomes
part of the resident's continuing identity.
