# Build City Studio over the city-pack tools

## Status

The command-line builder now supports real and fictional cities, structured validation, stable pack and
schema versions, travel hubs, route hub IDs, schematic previews, and noninteractive builds. San Francisco,
Portland, and Alderbank use the shared format. The engine exposes a read-only preview of the current pack.

The missing part is the draft editor and safe publication workflow.

## Goal

Give a steward a browser tool for building and reviewing a city before anyone inhabits it. City packs stay
portable files that can be exchanged and hosted without approval from a central catalog.

## Build next

1. Extract remaining reusable work from `build_city_pack.py` so the CLI and browser call the same builder
   and validator.
2. Add a node-local draft store outside the published pack directories.
3. Let a steward create, import, edit, validate, and preview a draft on a geographic or generated fictional
   map. Major 131 owns the deterministic field and section compiler used by that preview.
4. Export and import an immutable, versioned pack artifact.
5. Add a first-publication operation that refuses to overwrite a seeded or inhabited node.
6. Keep replacement of an inhabited pack blocked until a separate migration contract exists.
7. Document the tool publicly while keeping write access to a hosted node authenticated.

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
- [ ] The CLI and browser use one extracted build implementation rather than duplicated rules.
- [ ] A steward can save and preview a draft without touching a live pack.
- [ ] Packs can be imported and exported without a central catalog.
- [ ] First publication refuses a seeded or inhabited target.
- [ ] Replacing an inhabited city remains impossible without an explicit migration workflow.
- [ ] The studio has no resident-private read or write surface.
