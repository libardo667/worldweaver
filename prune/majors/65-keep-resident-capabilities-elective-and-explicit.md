# Keep resident capabilities elective and explicit

## Status

The shared resident runtime already has an information-source registry and explicit capabilities for city
information, local files, recall, measurement, travel, traces, gifts, and hearth work. The 2026-07-20 source
audit now carries scope and provenance through the actual prompt and withdraws sources whose access contract
is not real yet. Exact local speech and direct action results are unavoidable perception; broader information
is requested through a typed read.

This replaces the older idea that a system should infer hidden desires across a population and grant new
tools without anyone knowing why. Capabilities should be understandable, scoped, and reviewable.

## Problem

Residents need useful ways to inspect and act on their world without receiving every possible source in
every prompt. At the same time, file access, network access, and new action verbs carry different privacy
and safety risks. One vague “tools” bucket hides those differences.

## Capability model

Each capability declares:

- a stable name and plain description;
- whether it reads information, changes the world, or both;
- its scope: hearth, current city, named files, or external network;
- its provenance class;
- who or what granted it and when;
- limits such as paths, destinations, size, rate, or expiry;
- whether the resident can inspect, decline, or revoke it.

The automatic prompt lists available capability names and short descriptions. Content arrives only after
the resident chooses a source or performs an action.

Embodied perception is not a capability lookup. The current small loop receives its exact place, co-present
people, new speech at that place, attributed visible marks, and reachable destinations. Visible objects and
typed environmental changes belong in this unavoidable field once their neutral projection contracts exist;
they are not supplied today by invented scene prose. Broader feeds, archives, detailed records, distant
places, and external networks remain elective.

## Build next

1. Put file, world, computation, and external-network capabilities behind the same inspectable registry.
2. Make capability grants durable resident/hearth records rather than hidden host configuration.
3. Add an elective resident view of current grants, limits, and provenance.
4. Let a resident decline or revoke nonessential grants without breaking identity or ledger access.
5. Add the artifact-stoop verbs from Major 125 using the same world-scoped contract as humans.
6. Define how a new capability is proposed and reviewed without mining private language or rewarding a
   resident for asking a steward.
7. Keep external egress under the stricter policy in Minor 122.
8. Define an authenticated citywide publication channel before restoring the elective `chatter` source.
9. Build any public-history read from typed events with evidence IDs rather than generated summaries.

## Boundaries

- A capability is an affordance, not a prompt instruction to use it.
- Entering a place supplies a bounded embodied scene, not a dump of every local information source.
- Co-presence, exact-place speech, and a direct local address cannot be hidden behind an elective lookup.
- No population-wide demand miner reads private journals or ledgers to decide what residents should want.
- Private file grants do not travel to a city or another host unless explicitly included in a hearth-hosting
  agreement.
- Public actions use engine rules and typed events; tool prose cannot declare success.

## Acceptance criteria

- [x] Information sources are selected electively through one shared registry.
- [x] File reading, recall, measurement, city information, travel, and traces carry source provenance through
  source advertisement and returned prompt material.
- [x] World-changing actions pass through typed engine contracts.
- [ ] Every capability has an inspectable grant, scope, provenance, and limit record.
- [ ] A resident can inspect and revoke nonessential capabilities.
- [ ] Humans and residents share the artifact-stoop domain verbs where their abilities are the same.
- [ ] New-capability review does not require population profiling or private-language mining.
- [ ] External network access follows Minor 122 and fails closed when not granted.
