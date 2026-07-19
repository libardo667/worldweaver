# Build City Studio over the city-pack tools

## Status

The command-line builder now supports real and fictional cities, structured validation, stable pack and
schema versions, travel hubs, route hub IDs, schematic previews, and noninteractive builds. San Francisco,
Portland, and Alderbank use the shared format. The engine exposes a read-only preview of the current pack.

The folder-local operator can now inspect a generated-map release and publish only that additive drawing.
It verifies hashes, rejects active SVG content and invented routes, requires every canonical city-pack file
to remain byte-for-byte unchanged, refuses active resident agents, makes a full backup, and restarts the
backend. This closes the manual-copy gap found while testing Alderbank, but it is not the missing draft
editor or a general city-pack publication workflow.

City-pack assembly is now extracted from the command-line script. The reusable service accepts a city
configuration and optional source records, then returns validated pack files and the generated map entirely
in memory. It does not make network requests, touch the filesystem, or mutate the draft configuration. The
existing CLI handles optional OpenStreetMap retrieval and file output around that service. A fixed timestamp
makes the shared builder deterministic in tests, and Alderbank still produces the exact same map artifact.

The first private draft store is also in place. `python dev.py city-draft` can create, list, inspect, and
preview a draft, then unlock, reroll, and relock one fictional-map section. Drafts live under ignored
`data/city_drafts`, outside published packs. Each save assembles and validates a complete preview in a
temporary directory before replacing the prior draft, and every section gets its own cropped SVG preview.

The first City Studio browser boundary now runs as its own process with `python dev.py city-studio`. It binds
only to `127.0.0.1`, uses a fresh token for every run, checks host headers, and has no CORS or public-shard
mount. The page can create a draft from a checked-in configuration, view the full map, focus each local
section, and unlock, reroll, or relock it. Writes carry the expected draft revision so two stale views cannot
silently overwrite each other. Its routes touch city configurations and the private draft store only; they
do not read residents, accounts, the world database, or a published pack.

## Goal

Give a steward a browser tool for building and reviewing a city before anyone inhabits it. City packs stay
portable files that can be exchanged and hosted without approval from a central catalog.

## Build next

1. Add JSON import and ordinary place, route, landmark, and field-constraint editing to the local studio.
2. Improve geographic preview for real-city drafts; Major 131 continues to own generated fictional maps.
3. Export and import an immutable, versioned pack artifact.
4. Add a first-publication operation that refuses to overwrite a seeded or inhabited node.
5. Keep replacement of an inhabited pack blocked until a separate migration contract exists.
6. Document the tool publicly. Any future remotely hosted editor needs real steward authentication; the
   current studio deliberately remains local-only.

## Pack rules

- IDs, coordinates, paths, landmarks, transit, travel hubs, and cross-references are validated before
  publication.
- Ambiguous geography produces an error or warning; the builder does not silently invent a repair.
- A fictional pack never claims OpenStreetMap as its source.
- Generated fictional maps record their seed, compiler version, rule-library version, source licenses, and
  locked section boundaries.
- A destination city owns the mapping from its travel hub ID to its local entry place.
- Drafts remain local until deliberately exported or published.
- The federation may advertise a live pack version but does not own pack source or approve publication.

## Boundaries

- City Studio edits places and pre-habitation world structure, never resident identity or private state.
- A published inhabited version is read-only in the first studio.
- The studio is separate from the public commons client and private steward operations.
- `build_city_pack.py --all` remains a supported automation path.

## Acceptance criteria

- [x] The shared validator returns structured errors and warnings.
- [x] Packs have schema and pack versions, validated travel hubs, and route hub IDs.
- [x] Real and fictional packs use the same core builder and preview shape.
- [x] The CLI supports reproducible noninteractive builds.
- [x] The CLI and local browser use one extracted build and validation implementation rather than duplicated
  rules.
- [x] A steward can save and preview a draft with the local command, without touching a live pack. Browser
  controls remain to be built.
- [ ] Packs can be imported and exported without a central catalog.
- [ ] First publication refuses a seeded or inhabited target.
- [ ] Replacing an inhabited city remains impossible without an explicit migration workflow.
- [x] The studio has no resident-private read or write surface.
