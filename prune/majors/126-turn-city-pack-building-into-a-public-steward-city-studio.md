# Turn city-pack building into a public steward city studio

## Status

Active. The first implementation slice is the shared pack schema and validation layer needed by both the
command-line builder and a later browser studio.

## Problem

`worldweaver_engine/scripts/build_city_pack.py` can build San Francisco and Portland packs and is mostly
city-agnostic, but it is still a developer script:

- it mixes OpenStreetMap downloads, curated-data merging, validation, progress printing, and filesystem
  writes in one large file;
- there is no draft workspace, preview, validation report, or safe publish step;
- adding a city requires hand-editing a large JSON config;
- travel routes contain display labels but not destination-owned map entry points;
- a steward cannot see the city take shape before residents live there;
- rebuilding a pack gives no clear protection against changing the ground underneath an occupied city.

This hides one of the project's most useful public tools. A city pack is a portable description of a place,
not private operator plumbing. People should be able to make, inspect, refine, export, and host their own
packs without asking a central catalog for permission.

## Proposed Solution

Build a separate steward-facing City Studio around one shared city-pack build service.

### 1. Separate the build engine from its interfaces

Move reusable parsing, normalization, validation, OpenStreetMap import, preview assembly, and artifact
writing into ordinary service modules. Keep `build_city_pack.py` as a thin command-line interface over
that same code. The browser studio and tests must use the same rules rather than implementing a second
builder.

### 2. Give city packs an explicit versioned schema

Validate at least:

- stable city identity and manifest metadata;
- neighborhoods, coordinates, and adjacency references;
- transit, landmarks, and corridor references;
- travel hubs with a valid local entry location;
- inter-city routes with stable departure and arrival hub IDs;
- duplicate IDs, broken references, missing required fields, and unsafe path names.

Validation should return structured errors and warnings that a CLI or UI can render. It must not silently
repair ambiguous geography.

### 3. Use a draft -> preview -> publish workflow

A steward works on a draft outside the active runtime pack directory. They can:

- start from a small city form, an imported config, or an existing pack;
- fetch and merge OpenStreetMap data;
- edit curated neighborhoods, landmarks, routes, and travel hubs;
- preview the resulting map and inspect validation problems;
- export the draft as a portable artifact;
- publish an immutable pack version when it is ready.

Draft and preview operations must never alter a live city.

### 4. Make first publication safe and later replacement explicit

The initial studio is for founding a city before residents inhabit it. Publishing must fail closed if the
target node already has live sessions, resident attachments, or an existing seeded world unless a later
migration workflow explicitly handles that state. Do not add a casual “rebuild live city” button.

Published versions remain available for rollback. A node chooses which local pack version it hosts; the
federation root does not approve packs or store their source workspace.

### 5. Keep the studio separate from the commons interface

This is an authenticated steward-authoring surface, not the ordinary human view and not a resident
surveillance console. It may edit a city before habitation, but it may not edit resident souls, prompts,
drives, memories, or behavior targets. Once residents inhabit a version, the studio becomes read-only for
that live version until a real migration contract exists.

The tool itself should be publicly documented, easy to run locally, and capable of importing/exporting
packs without a WorldWeaver account or central service. Write access to a hosted node remains steward-only.

### 6. Let city-owned travel hubs finish the arrival contract

Each city pack defines its own travel hubs. A hub has a stable ID, display name, supported modes, and a
valid local `entry_location`. Inter-city routes reference a local departure hub ID and a destination hub
ID. On arrival, the destination resolves that ID through its own pack instead of trusting source-authored
display text as a map location.

This preserves federation: routes describe possible connections, destination packs own their geography,
and live nodes merely advertise which pack they currently host.

## Files Affected

- `worldweaver_engine/scripts/build_city_pack.py`
- new `worldweaver_engine/src/services/city_pack_builder.py` and validation/schema modules as needed
- `worldweaver_engine/src/services/city_pack_service.py`
- `worldweaver_engine/scripts/city_configs/*.json`
- `worldweaver_engine/data/cities/*`
- current shard copies under `shards/*/data/cities/*`
- new steward city-studio API routes
- a separate city-studio client surface and API client types
- `prune/majors/37-formalize-actor-scoped-cross-shard-travel-and-runtime-transfer.md`
- `prune/majors/71-steward-facing-semi-public-portal-witness-shadow-and-threshold.md`
- builder, API, migration-safety, and client tests

## Acceptance Criteria

- [ ] The CLI and browser studio use one shared pack-building and validation implementation
- [ ] A steward can create and save a draft without touching any published or active pack
- [ ] A draft can be previewed on a map before publication
- [x] Validation returns structured errors and warnings for broken IDs, coordinates, and references
- [ ] Every published pack has a stable city ID, schema version, and immutable pack version
- [x] Each local travel hub resolves to a valid local entry location
- [x] Inter-city routes reference stable departure and arrival hub IDs rather than relying on display text
- [ ] The destination node resolves its arrival hub through its own pack
- [ ] First publication is blocked when the target already has residents or a seeded live world
- [ ] Replacing an inhabited city requires a separate explicit migration workflow
- [ ] Drafts and source configs remain node-local unless deliberately exported
- [ ] Packs can be exported and imported without registration in a central catalog
- [ ] The city studio is separate from the ordinary commons UI and exposes no resident-private internals
- [x] `build_city_pack.py --all` remains a supported non-interactive workflow
- [x] Existing San Francisco and Portland packs pass the new validator

## Risks & Rollback

- A visual editor can hide bad geography behind a friendly form. Keep the structured validation report
  authoritative and show errors directly.
- Publishing over an inhabited pack can strand residents or invalidate locations. Fail closed until a
  migration design exists.
- OpenStreetMap imports can produce noisy or enormous drafts. Keep imported data reviewable and separate
  from curated choices.
- A central gallery can become an approval gate. Import/export must work directly between stewards and
  nodes without federation permission.
- The studio can drift into resident control tooling. Its write scope ends at city/world structure and
  pre-inhabitation configuration.
- Roll back by retaining the thin CLI and published-pack reader while disabling draft write and publish
  endpoints. Published artifacts remain ordinary portable files.

## Build log — 2026-07-17

- Added one structured validator that returns path-specific errors and warnings suitable for both a CLI
  and browser UI.
- Made `build_city_pack.py` validate its complete in-memory pack before writing any output files.
- Added schema version `1.1.0`, `travel_hubs.json`, and stable route hub references.
- Gave the San Francisco and Portland packs valid local travel hubs and verified their entry neighborhoods.
- Kept display labels for people while adding IDs for machine-safe departure and arrival.
- Added runtime hub lookup and exposed hubs through the existing full-map response.
- Kept `--all` and `--offline`; an offline Portland build now proves the curated baseline passes the same
  validator.

The visual draft workspace, preview API, publishing gate, and client surface are still open. The current
slice deliberately makes the reusable rules trustworthy before adding writes through a browser.
