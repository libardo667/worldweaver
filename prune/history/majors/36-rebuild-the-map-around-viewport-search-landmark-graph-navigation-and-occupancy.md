# Rebuild the map around viewport search, landmark graph navigation, and occupancy

## Status

This major now materially supersedes Major 06.

The earlier "agent life visibility" map work described a useful frontend
symptom, but the active problem is broader: viewport retrieval, landmark graph
coherence, truthful occupancy, and substrate-neutral presence all belong to one
map architecture pass.

## Problem

The current map works exactly as implemented, but the implementation is too narrow.

Today the map is built from a static neighborhood graph plus a bolt-on "Nearby"
landmark search:

- the client calls `getNearbyLandmarks(location, radiusKm=0.75)` from
  `worldweaver_engine/client/src/api/wwClient.ts`
- `App.tsx` merges those nearby landmarks into the visible node list
- `LocationMap.tsx` renders them as isolated markers
- the backend endpoint `/api/world/landmarks/nearby` in
  `worldweaver_engine/src/api/game/world.py` is anchored to one named location
  and a fixed-radius haversine search

This creates three user-visible failures:

1. The "Nearby" button is not actually a useful discovery tool.
   It sends a small radial pulse around the player's current location rather than
   searching the area the player is actually looking at on the map.

2. Landmark navigation is graph-incoherent.
   Landmarks are often shown as extra markers, but not as properly connected map
   nodes. Once a player navigates to a landmark, the graph behaves strangely and
   travel often requires hopping back through the coarse neighborhood skeleton.

3. Occupancy is incomplete and privacy semantics are inconsistent.
   Agent-occupied landmark nodes such as Clement Street can be effectively
   invisible if they are outside the tiny nearby radius or absent from the static
   graph merge. When occupancy is shown, the map should expose "there are people
   here" without distinguishing human vs AI by node rendering.

4. Non-dev UI surfaces currently leak ontology that should stay operational.
   Outside explicit developer/operator diagnostics, the interface should not tell
   players who is human and who is AI. The current `Presence` tab is useful, but
   it should become a true presence surface rather than an entity-type surface.

The result is that the map is usable for rough neighborhood travel but not yet a
real city exploration interface. It feels like a graph viewer with a landmark
escape hatch instead of a living navigable city surface.

## Proposed Solution

Replace the current nearby-landmark bolt-on with a viewport-aware, search-aware
map retrieval model that returns a coherent local subgraph of neighborhoods and
landmarks, with occupancy layered on top.

### Phase 1 - Introduce viewport-scoped map retrieval

Add a backend map query surface that accepts the current viewport and returns the
 relevant local graph slice.

The query should support:

- viewport bounds
  - north / south / east / west or equivalent bbox format
- optional semantic search text
  - place name
  - category (`food`, `drink`, `park`, etc.)
  - vibe / descriptor terms supported by the city pack metadata
- optional filters
  - occupied only
  - landmarks only
  - neighborhoods only

This should replace the current "search a 0.75 km bubble around my current
location" behavior for map exploration.

Important constraint:

- the retrieval surface should be map-driven, not player-location-driven
- if the user pans to another district, the map query should follow the viewport

### Phase 2 - Return a coherent mixed graph, not orphaned landmark markers

When the viewport query returns landmarks, it must also return the graph links
that make those landmarks navigable in context.

That means:

- landmarks should not arrive as disconnected marker-only add-ons
- the backend should emit neighborhood-to-landmark and landmark-to-landmark
  edges where navigation is valid
- the client should render one coherent graph surface from the returned nodes and
  edges rather than merging a static graph with an orphan list

The target behavior is closer to a local city graph:

- neighborhoods remain major anchors
- landmarks become real navigable subnodes
- travel does not require unnatural "bounce back to a neighborhood node first"
  unless that is actually the graph truth

### Phase 3 - Add semantic map search over city-pack metadata

Searching the map should query the city pack and world graph as a real place
search, not just filter whatever nodes happen to already be loaded into the
client.

The search system should support:

- exact place-name lookup
- partial place-name match
- category match (`tea`, `coffee`, `bar`, `groceries`, `park`, `transit`)
- vibe / description terms from city-pack metadata
- search within viewport first, then optionally outside viewport

The result set should be able to:

- update the visible graph slice
- center the map on matched places
- make those places navigable immediately

This should make "find food", "find tea", "find Clement Street", or "find a quiet
park nearby" first-class map interactions.

### Phase 4 - Make occupancy map-wide and substrate-neutral

The map should be able to show all occupied nodes when desired, including:

- neighborhood nodes
- landmark nodes
- player and resident presence on either kind of node

Occupancy display rules:

- show occupancy count wherever people are actually present
- do not distinguish human vs AI in the map marker treatment
- preserve aggregate counts and names in tooltips where appropriate
- avoid hiding landmark occupancy just because the landmark is not part of the
  coarse default neighborhood graph

This privacy rule should apply across all non-dev UI surfaces:

- map markers
- map tooltips
- presence tab
- shard/world presence summaries

Only explicit dev/operator diagnostics should retain human-vs-AI distinctions.
Normal player-facing UI should describe presence, activity, and location, not
entity substrate.

This means occupancy must be layered onto the same node-retrieval model used by
the map itself, not only the static graph payload.

### Phase 5 - Replace "Nearby" with map-native exploration controls

The current "Nearby" button should be rethought entirely.

Possible end state:

- `Search this area`
- `Show occupied`
- `Show food / drink / parks / transit`
- `Expand around current view`

The important point is that the control should describe what it really does.
"Nearby" is too tied to the current flawed implementation.

The player should be able to:

- pan to an area
- ask for search results in that area
- see the graph update accordingly
- travel through the resulting graph naturally

### Phase 6 - Preserve default readability

The map should still open to a readable city surface even before the player uses
search or viewport expansion.

That means:

- default neighborhood graph remains a useful starting layer
- landmark density should not overwhelm the initial view
- semantic or viewport expansion should be additive and reversible
- filters should be easy to clear

The redesign is not "show every node all the time." It is "make the user capable
of exploring any local area of the graph intentionally."

### Phase 7 - Normalize presence UI around presence, not substrate

Update the non-dev presence surfaces so they speak in terms of:

- who is here
- who is active
- who is resting
- where activity is concentrated

and not in terms of:

- human
- AI
- agent
- visitor classes that reveal substrate

The `Presence` tab should remain rich, but it should read as a social presence
surface rather than a simulation debugger. Developer-only surfaces can retain
the richer ontology for debugging and stewardship.

## Files Affected

- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/components/LocationMap.tsx`
- `worldweaver_engine/client/src/components/PresencePanel.tsx`
- `worldweaver_engine/client/src/api/wwClient.ts`
- `worldweaver_engine/client/src/components/EntryScreen.tsx`
- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/src/services/city_pack_service.py`
- city-pack metadata/query helpers used to classify landmarks, categories, and vibes
- any map/navigation tests covering nearby landmarks, graph retrieval, and occupancy rendering

## Acceptance Criteria

- [ ] The map can request nodes based on the current viewport rather than only the player's current location
- [ ] Searching for a place/category/vibe updates the visible graph with relevant local nodes and edges
- [ ] Landmark nodes returned by the map query are graph-connected and directly navigable where appropriate
- [ ] Traveling to a landmark no longer forces unnatural neighborhood-only escape behavior unless the graph itself requires it
- [ ] Occupied landmark nodes appear on the map when occupancy display is enabled
- [ ] Map occupancy does not visually distinguish human vs AI presence at the node level
- [ ] Non-dev UI surfaces do not disclose whether a present character is human or AI
- [ ] The `Presence` tab describes presence/activity/location without substrate labels
- [ ] The old nearby-radius behavior is removed or demoted behind a more accurate exploration control
- [ ] The default map remains readable without flooding the player with every landmark in the city

## Risks & Rollback

- A viewport-driven map query could become too heavy if it naively scans too many
  nodes every pan/zoom event. Roll back by debouncing client requests and limiting
  query cadence.
- Over-connecting landmarks could make the graph less truthful. Roll back by
  deriving edges from explicit city-pack semantics instead of inventing generic
  local links.
- Map search could turn into a second disconnected search system. Roll back by
  keeping it grounded in city-pack/world-node metadata rather than inventing a
  separate index with incompatible semantics.
- Showing all occupied nodes could clutter the map. Roll back by making occupancy
  display an explicit layer/filter while keeping the retrieval model capable of
  including landmark occupancy when requested.
