# Generate fictional maps from stable fields and local sections

## Status

Alderbank currently uses real latitude/longitude values on a blank Leaflet canvas. Neighborhood paths,
landmark containment, and live presence are reduced to dots and identical lines. This is enough to test
movement but does not communicate a river town. It also exposed three concrete client bugs: overlapping
places could trade visual positions when presence changed, containment links looked like walking paths, and
the theme button covered the place panel's close button.

The first cleanup slice fixed those three failures. The first map compiler is now built and published as an
additive drawing over Alderbank's existing movement graph. It produces stable terrain fields, a river,
region cover, required place anchors, canonical routes, twelve independently seeded sections, typed section
connectors, a hashed JSON artifact, and a hashed SVG.

The second map slice gives each canonical neighborhood edge an optional name, path type, and required
landmark waypoint. The compiler refuses display metadata for a path that does not exist in the city graph,
and the pack validator refuses an artifact whose drawn route set differs from that graph. Alderbank now
draws River Path, Footbridge Path, and Pineward Path and keeps permanent labels on its four main places.

The generated node operator now has explicit `map inspect` and `map publish` commands. Publication verifies
the city, pack version, artifact and SVG hashes, passive SVG content, and canonical routes; refuses changes
to non-map city files or publication while residents run; makes a full backup; and reloads the backend.

Alderbank is the project's experiment town. On 2026-07-19, the project owner explicitly approved using the
inhabited Alderbank shard for this work. That approval is narrow: the generated drawing may change while we
learn, but accounts, objects, marks, doors, named places, and movement edges remain canonical engine state
and must survive each deployment.

## Problem

Fictional cities need a map that explains their shape without pretending to be OpenStreetMap geography.
The city pack already knows named places, adjacency, landmarks, regions, rivers in prose, and required travel
connections, but the renderer has no terrain, route types, districts, labels, or stable treatment of nested
places.

A single unconstrained procedural pass would create a second problem: it could draw doors, paths, bridges,
or buildings that the engine does not actually support. It would also be difficult to revise one district
without rearranging the entire town.

## Proposed solution

Build a deterministic map compiler in layers.

1. Treat the published city pack as the source of truth for named places, movement edges, barriers, doors,
   travel hubs, and required landmarks.
2. Generate stable low-resolution physical fields such as elevation, water flow, wetness, broad soil class,
   and exposure. Keep only fields that change visible layout or a declared game rule.
3. Derive regions and suitability from those fields: riverbank, flood area, orchard ground, woods, village
   center, steep ground, and buildable ground.
4. Fit required city-pack facts into suitable sites. Top-down requirements may adjust generated fields
   within declared limits; the compiler may not omit a required bridge, mill, commons, or route.
5. Divide the map into independently seeded sections. Each section declares typed boundary connectors such
   as river, road, footpath, elevation band, and vegetation edge.
6. Use local constraint generation, including optional Wave Function Collapse, to fill buildings, paths,
   fields, vegetation, and decorative detail inside each section. Adjacent sections must agree at their
   boundary connectors.
7. Validate that every visible interactive route, doorway, landmark, and barrier matches an engine fact.
   Decorative features are explicitly noninteractive.
8. Compile the result into an immutable, versioned artifact containing the source pack version, seed,
   generator version, rule-library hash, field layers, section manifests, final geometry, and validation
   report.

The human client should also become place-first. The current place and its available verbs are the default
surface. A full-screen map is an optional destination and orientation view, not the permanent background
for every interaction.

## Build order

1. Finish map correctness: stable overlap offsets, typed edges, visible close/map controls, labels, and a
   clear distinction between walkable routes and containment.
2. Make the current place and its verb palette the default participant view; open and close the map
   deliberately without changing the participant's location.
3. Define a small generator input schema and compiled-map artifact. Start with elevation, river/watershed,
   region, required-anchor, and route layers.
4. Build a deterministic Alderbank map using authored constraints and simple procedural rules before adding
   WFC. **Done for the first field-map version.**
5. Add section manifests, stable per-section seeds, boundary connectors, local reroll, and lock controls.
6. Add an optional WFC detail pass using project-owned or license-compatible rule libraries. OSM-derived
   pattern libraries require recorded source, attribution, and an explicit ODbL review.
7. Integrate generation, validation, preview, reroll, locking, and export into City Studio.
8. Publish the additive map layer to the explicitly approved Alderbank experiment shard. Replacing canonical
   inhabited-city geometry still requires a separate migration contract.

## Files affected

- `worldweaver_engine/client-public/src/components/WorldMap.tsx`
- `worldweaver_engine/client-public/src/components/PlacePanel.tsx`
- `worldweaver_engine/client-public/src/App.tsx`
- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/src/services/city_pack_service.py`
- `worldweaver_engine/src/services/map_generation/` (new)
- `worldweaver_engine/scripts/build_city_pack.py`
- `worldweaver_engine/scripts/city_configs/*.json`
- the future City Studio client described by Major 126
- `worldweaver_engine/tests/`

## Boundaries

- The engine topology wins over generated appearance. A drawing cannot create an affordance.
- Generation is deterministic for the same pack, seed, generator version, and rule library.
- One section can be regenerated without moving locked sections.
- Failure or contradiction stays local and produces a clear validation error or a plain deterministic
  fallback; it does not silently rewrite required town facts.
- Weather and seasons may change presentation but do not regenerate permanent geography.
- Environmental fields shape maps without automatically creating hunger, injury, deprivation, or resident
  scoring.
- Draft generation normally happens before habitation. Alderbank is the explicit experiment exception, but
  its canonical inhabited state remains immutable until a reviewed migration exists.
- OSM may inform morphology or provide licensed source data, but fictional maps never claim to be real OSM
  places and always retain required attribution and source records.

## Acceptance criteria

- [x] Overlapping nodes keep stable visual positions when presence or API ordering changes.
- [x] The map response distinguishes walking paths from place containment, and the client does not draw
  containment as a route.
- [x] A visible control can close the place panel and reveal the full map.
- [ ] The ordinary human surface starts at the current place and presents available verbs without requiring
  the map to remain open.
- [ ] A fictional-map source schema declares seeds, physical fields, required anchors, section boundaries,
  and rule-library versions.
- [x] The same compiler inputs produce byte-stable or canonically equivalent artifacts.
- [x] Alderbank preview shows a river, terrain regions, typed paths, named landmarks, and stable labels while
  preserving its current movement graph.
- [ ] Each section can be previewed, rerolled, and locked independently without moving locked neighbors.
- [ ] Section seams match for routes, waterways, elevation bands, and region edges.
- [x] Every visible interactive route is backed by a canonical engine fact. Doorway drawing remains future
  work; current doors are exposed through the place controls rather than drawn on the map.
- [ ] City Studio can export a validated versioned map artifact without mutating an inhabited shard.
- [x] The approved Alderbank experiment shard can publish and serve the generated artifact without running
  the generator at page load.

## Risks and rollback

Generated terrain can become a large subsystem with no participant value. Keep the first Alderbank compiler
small and require every field to affect visible output or a declared rule. WFC contradictions can be
expensive or nondeterministic; run them section by section with bounded retries and a plain fallback.

The current city-pack graph and simple schematic renderer remain the rollback path. Compiled artifacts are
additive until the preview, validator, and first-publication flow are proven. Existing inhabited shards keep
their published geometry throughout this work.
