---
title: Federation without ownership
sidebar_position: 3
---

# Federation without ownership

WorldWeaver is intended to be a network of nodes run by different stewards, not one service that owns every
city and resident.

## What a directory does

A federation directory can publish:

- which nodes recently checked in;
- which city pack each node hosts;
- the public HTTPS address used for travel;
- the travel hubs and routes a node advertises.

It helps participants find one another. It does not own cities, residents, hearths, or their private data.
`world-weaver.org` may operate an early directory, but the protocol must permit other directories and direct
peer discovery.

## What a city node owns

A city node is authoritative for its own local facts: places, sessions, objects, speech, access rules, and
events that occurred there. Those facts do not travel as part of a resident.

## What travels

Travel carries stable actor identity and a verifiable handoff. The destination creates a new local session
for that actor. The resident's private ledger and hearth remain resident-held rather than being copied into
the federation registry.

## What remains to build

The local handoff protocol works between containers on one machine. An open network still needs:

1. a key pair and stable identity for every node;
2. signed registration and handoff requests;
3. HTTPS ingress and address rotation;
4. trust and revocation rules that do not depend on one shared secret;
5. resident-host authorization and recovery;
6. discovery that tolerates more than one directory.

Until those exist, the current federation is a development topology, not a secure decentralized network.
