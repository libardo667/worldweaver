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
memory, workshop, and optional local grants. A host may place an explicitly enabled prompt diagnostic under
the same folder while it runs, but that file is not resident continuity and does not travel with the hearth.

The local filesystem boundary is enforced as well as described: the hearth and its directories are owner-only
`0700`, and its regular files are owner-only `0600`. Startup repairs older active homes without following
symbolic links outside them, and clean shutdown repairs files created during the run.

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

## Identity growth belongs to the hearth

The hearth's `identity/soul_growth.md` file is the authoritative mutable identity layer. A city cannot
replace it during arrival or travel. If an older deployment stored growth in a city database, the resident
can migrate that text into an empty hearth once; after that the old city row is only historical input.

Residents can still stage self-edit proposals in their private ledgers. WorldWeaver does not currently
promote those proposals automatically. At the hearth, the resident can privately inspect one accepted
identity proposal and the exact ledger events that produced it. If they then make the explicit adoption
action shown with that proposal, WorldWeaver appends the resident's original words to `soul_growth.md`,
refreshes the live prompt identity, and records the proposal, inspection, and adoption IDs. The action is
not available in a city. Repeated wording is context, not evidence or automatic approval.
