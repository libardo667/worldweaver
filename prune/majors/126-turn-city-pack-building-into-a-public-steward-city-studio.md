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

## Goal

Give a steward a browser tool for building and reviewing a city before anyone inhabits it. City packs stay
portable files that can be exchanged and hosted without approval from a central catalog.

## Build next

1. Add a node-local draft store outside the published pack directories.
2. Let a steward create, import, edit, validate, and preview a draft on a geographic or generated fictional
   map. Major 131 owns the deterministic field and section compiler used by that preview.
3. Export and import an immutable, versioned pack artifact.
4. Add a first-publication operation that refuses to overwrite a seeded or inhabited node.
5. Keep replacement of an inhabited pack blocked until a separate migration contract exists.
6. Document the tool publicly while keeping write access to a hosted node authenticated.

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
- [ ] City-pack assembly and validation now have one extracted implementation used by the CLI. This becomes
  complete when the browser calls it too rather than duplicating its rules.
- [ ] A steward can save and preview a draft without touching a live pack.
- [ ] Packs can be imported and exported without a central catalog.
- [ ] First publication refuses a seeded or inhabited target.
- [ ] Replacing an inhabited city remains impossible without an explicit migration workflow.
- [ ] The studio has no resident-private read or write surface.
