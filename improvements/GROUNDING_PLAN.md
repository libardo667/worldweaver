# WorldWeaver Grounding Plan — Real Bones, Emergent Flesh

## The Problem

WorldWeaver currently generates geography from pure vibes. When a resident says
"I walk to Ocean Beach," the narrator invents Ocean Beach from nothing. This
produces beautiful prose but geographically incoherent worlds — transit systems
that don't connect, neighborhoods that drift, distances that make no sense,
and a city that contradicts itself across sessions.

When a human player tries to travel from San Francisco to Portland, the narrator
has no skeleton to hang the journey on. It hallucinates waypoints. The world
feels like a dream — vivid but unreliable.

## The Vision

**Real city bones, fictionalized room-temperature flesh.**

Ground the world in actual geography, transit, weather, and civic events.
Let the narrator invent interiors, characters, social rituals, rumors, and
relationships. The bones are real. The people are emergent.

A resident who "takes BART to the Mission" arrives somewhere that maps to
reality. A resident who "walks to Ocean Beach" experiences fog that's actually
there today. A resident who "takes the Coast Starlight to Portland" follows
a real route at a plausible speed.

But the taqueria they find in the Mission? The cashier's name? The way the
light hits the salsa bar? That's the narrator's domain. Grounded geography
gives the narrator a scaffold; it doesn't replace the narrator's imagination.

## Three-Layer World Model

### Layer 1: Ground Truth Anchors (seeded once, cached aggressively)

Precomputed metro skeleton from real geospatial data:

- **Neighborhoods/districts** with rough boundaries and vibes
- **Street graph** — major corridors, intersections, walkability
- **Transit nodes** — BART stations, Muni stops, bus corridors, Amtrak stations
- **Parks / waterfronts / landmarks** — Golden Gate Park, Ocean Beach, Ferry Building
- **POI categories** — "there are taquerias in the Mission" (not specific businesses)
- **Travel adjacency** — what connects to what, rough travel times
- **Inter-city corridors** — SFO→PDX by train (11h), by air (90min), by car (10h)

This layer is **expensive to build, cheap to serve.** Build it once per city
from OpenStreetMap data, cache it as a local JSON/SQLite graph, and never
hit external APIs at runtime for this data.

### Layer 2: Canonical World Facts (reducer-owned, grows through play)

The reducer's world fact graph, now enriched with grounding metadata:

- "La Espiga Dorada exists at the corner of 24th and Mission" (emergent, committed)
- "This block smells like charred pork at lunch" (emergent, committed)
- "BART is running 12-minute delays today" (grounded, injected by weather/transit daemon)
- "Reyna and Mateo work here" (emergent, committed by doula)
- "It is foggy today" (grounded, injected by weather daemon)
- "Protest activity on Market Street" (grounded, injected by events daemon)

### Layer 3: Scene Invention (narrator, ephemeral, per-turn)

The narrator creates:

- What the window light feels like right now
- What the salsa verde does to the back of your throat
- What the kitchen sounds like
- Who is working today and what mood they're in
- Body language, ambient sound, sensory texture

This layer is cheap, fast, and disposable. It references Layers 1 and 2
but doesn't persist unless the reducer commits something notable.

## Fact Confidence Tiers

Extend the existing clarity levels with grounding-aware tiers:

| Tier | Source | Mutability | Example |
|------|--------|------------|---------|
| `grounded_geo` | Geospatial seed | Immutable | "BART connects SFO to Powell" |
| `grounded_weather` | Live weather API | Refreshed hourly | "Dense fog advisory today" |
| `grounded_transit` | Live transit feed | Refreshed per cycle | "BART delays on yellow line" |
| `grounded_event` | Structured event feed | Refreshed daily | "Protest downtown this afternoon" |
| `committed` | Reducer | Player-triggered | "Reyna works at La Espiga Dorada" |
| `derived` | Narrator inference | Soft | "The Mission smells like rain and tortillas" |
| `rumor` | Agent correspondence | Social | "I heard the cafe on Valencia is closing" |

The narrator and residents see all tiers but respond to them differently.
Grounded facts are authoritative. Committed facts are canon. Derived and
rumor facts are soft and can be revised.

## The Readable Map

### Every resident and human has access to a map

The map is a **queryable, expandable representation** of the world the
character knows about. It is NOT a static image. It is a structured object
the agent's context can include selectively.

**What the map contains:**

```
{
  "known_locations": [
    {
      "id": "la-espiga-dorada",
      "name": "La Espiga Dorada Taqueria",
      "neighborhood": "Mission District",
      "grounding": "emergent",
      "connections": ["24th-and-mission", "bart-24th-st"],
      "last_visited": "2026-03-10T19:28:00Z",
      "notes": "Window table has the best light. Mateo runs the kitchen."
    }
  ],
  "known_neighborhoods": [
    {
      "id": "mission-district",
      "name": "The Mission",
      "grounding": "grounded_geo",
      "vibe": "Vibrant Latino community, murals, taquerias, gentrification tension",
      "adjacent_to": ["soma", "castro", "potrero-hill", "noe-valley"]
    }
  ],
  "known_transit": [
    {
      "id": "bart-24th-st",
      "name": "24th Street Mission BART",
      "grounding": "grounded_geo",
      "lines": ["yellow", "green", "blue"],
      "connects_to": ["bart-16th-st", "bart-glen-park"]
    }
  ]
}
```

**How residents use it:**

The slow loop can "consult the map" as part of its context — a compressed
summary of what this character knows about the world's geography. This
informs movement decisions without the character needing to hallucinate
whether BART goes to the airport.

The fast loop does NOT see the full map. It sees only the current location
and immediate surroundings. The fast loop doesn't plan routes.

### Map expansion through play

When a resident or human suggests a new location — "I walk to Dolores Park"
— and that location isn't in the map yet:

1. **Framework intercepts** the location reference (parsing from the action text)
2. **Grounding query fires** (cached or one-time API call):
   - Is "Dolores Park" a real place in the current city?
   - If yes: pull neighborhood, coordinates, basic attributes
   - If no: let the narrator invent it (mark as `emergent`)
3. **New grounded node created** in the map with:
   - Geographic anchor (lat/lon, neighborhood)
   - Adjacency connections (what's nearby)
   - Category/vibe (park, green space, popular on weekends)
   - Weather context (pulled from current weather for that area)
4. **Reducer commits** the new location to the world fact graph
5. **All residents' maps update** — the new location is now discoverable

This means the explorer resident is literally expanding the shared map
for everyone. They walk to Ocean Beach → grounding query runs → Ocean Beach
node appears → now every resident can "go to Ocean Beach" with grounded
context.

## Live World Pulse — Weather, Transit, Events

### Architecture: Grounding Daemon

A background process (or async loop in the main daemon) that periodically
ingests real-world data and translates it into WorldWeaver-native facts.

```
grounding_daemon
├── weather_ingester     → NWS alerts API + Open-Meteo forecasts
├── transit_ingester     → GTFS realtime feeds (BART, Muni)
├── events_ingester      → GDELT structured events (optional v2)
└── fact_emitter         → POST /api/world/grounding/inject
```

**Key principle: ingest sparingly, cache aggressively, transform into
world pressures rather than raw data.**

### Weather (first-class, implement first)

**Sources:**
- U.S. National Weather Service alerts API (free, public, designed for redistribution)
- Open-Meteo forecast API (free, no key required, HRRR + GFS models)

**Ingestion cadence:** Every 30-60 minutes (NWS recommends no more than
1 request per 30 seconds; we need far less)

**Transform pipeline:**

```
NWS: "Dense Fog Advisory until 11 AM"
  → grounded_weather fact: {condition: "dense_fog", severity: "advisory",
     expires: "11:00 AM", location: "san_francisco"}
  → narrator pressure: "The fog hasn't burned off yet. Visibility is low."
  → resident effects:
    - Mateo: fewer customers, quiet morning
    - Reyna: can't see the view from the window seat
    - Explorer: navigation is harder, coastline invisible
    - Rowan: notices the fog and writes about thresholds
```

**Cache strategy:**
- Cache weather response for the polling interval (30-60 min)
- Store as grounded facts in the world fact graph
- Narrator reads from the fact graph, not from the API

### Transit (second priority)

**Sources:**
- BART GTFS-realtime feed (free, public)
- Muni NextBus API (free)

**Ingestion cadence:** Every 5-15 minutes during active play, disabled overnight

**Transform:**

```
BART realtime: "12 min delay on Yellow Line due to equipment"
  → grounded_transit fact: {line: "yellow", delay_minutes: 12,
     cause: "equipment", stations_affected: ["powell", "civic-center"]}
  → narrator pressure: "The platform is more crowded than usual"
  → resident effects: characters waiting longer, complaining, rerouting
```

### News/Events (optional, v2)

**Sources:**
- GDELT (structured, georeferenced, updates every 15 min)
- NOT raw news articles — structured event records only

**Transform into world pressures, not headlines:**

```
GDELT: protest event, downtown SF, 500+ participants
  → grounded_event fact: {type: "protest", location: "downtown",
     scale: "large", topic: "housing"}
  → narrator pressure: "There's extra foot traffic downtown today"
  → resident effects:
    - Explorer: follows the commotion
    - Margot: mentions it in a letter
    - Transit: reroutes near the area
```

**Critical rule: never mirror headlines literally.** Transform external events
into local consequences. A march affects foot traffic. A heat advisory changes
plans. Airport delays reshape who arrives where.

## Caching Strategy

### Three cache layers

**Layer 1: Seed cache (permanent, local)**

The city skeleton. Built once from OpenStreetMap/geospatial data. Stored as
local JSON or SQLite. Never expires. Never hits an external API at runtime.

```
data/cities/san_francisco/
├── neighborhoods.json      (40-60 entries)
├── transit_graph.json      (stations, lines, connections)
├── landmarks.json          (parks, bridges, waterfronts)
├── street_corridors.json   (major streets with vibes)
└── inter_city.json         (connections to other city packs)
```

**Layer 2: Live cache (TTL-based, refreshed by grounding daemon)**

Weather, transit status, active alerts. Stored in-memory or in the world
fact graph with TTL metadata.

```python
CACHE_TTL = {
    "weather": 3600,        # 1 hour
    "weather_alerts": 1800, # 30 minutes
    "transit_realtime": 300, # 5 minutes
    "events": 3600,         # 1 hour
}
```

When a cache entry expires, the grounding daemon refreshes it on next cycle.
Between refreshes, the narrator uses the cached version. Stale-but-usable
is better than blocking on an API call.

**Layer 3: Expansion cache (per-query, deduplicated)**

When a resident suggests a new location, the grounding query result is cached
permanently in the seed layer. The same location is never queried twice.

```python
# Before querying external API:
if location_id in seed_cache:
    return seed_cache[location_id]  # already grounded

# Query once, cache forever:
result = await geocode(location_name, city="San Francisco")
seed_cache.add(result)
world_graph.commit_grounded_node(result)
```

### API budget awareness

| Source | Rate limit | Cost | Strategy |
|--------|-----------|------|----------|
| OpenStreetMap Nominatim | 1 req/sec, no bulk | Free (ODbL) | Seed import only, never runtime |
| NWS Alerts API | "reasonable" | Free | Poll every 30-60 min |
| Open-Meteo | Generous | Free, no key | Poll every 30-60 min |
| BART GTFS-rt | Generous | Free | Poll every 5-15 min |
| GDELT | Every 15 min update | Free | Poll every 30-60 min |

**Total external API calls per hour during active play: ~10-20**

That's negligible. The caching strategy means the grounding layer adds
almost zero cost to the system.

### Licensing notes

- **OpenStreetMap data** is under ODbL. If you redistribute the seed graph
  as data (e.g., in city packs), attribution and share-alike apply. If it's
  internal infrastructure only, obligations are lighter. Decide early.
- **NWS data** is U.S. government work, public domain, explicitly designed
  for redistribution into decision-support tools.
- **Open-Meteo** is open-source (AGPL for the server, data is free to use).
- **GDELT** is free for research and commercial use.

## Grounding API — New WorldWeaver Endpoints

### Inject grounded facts

```
POST /api/world/grounding/inject
{
    "facts": [
        {
            "type": "grounded_weather",
            "location": "san_francisco",
            "data": {"condition": "fog", "temp_f": 58, "wind_mph": 12},
            "ttl_seconds": 3600,
            "source": "nws"
        }
    ]
}
```

### Query the map

```
GET /api/world/map/{session_id}
```
Returns the locations, neighborhoods, and transit nodes this session
has discovered or that are within grounded range of their current location.

### Suggest new location (triggers grounding query)

```
POST /api/world/map/expand
{
    "session_id": "...",
    "suggested_location": "Dolores Park",
    "context": "I want to walk there from the Mission"
}
```
Returns the newly grounded node (or existing node if already known).
Runs the geocoding query, caches the result, commits to the fact graph.

### Get current world pulse

```
GET /api/world/pulse
```
Returns current weather, transit status, and active events for the world's
city. Narrator and residents use this to stay situationally aware.

## City Packs — Productization

A **city pack** is a pre-seeded Layer 1 skeleton for a specific metro area.

### Pack contents

```
city_pack_san_francisco/
├── manifest.json           (city name, bounds, version, license)
├── neighborhoods.json
├── transit_graph.json
├── landmarks.json
├── street_corridors.json
├── poi_categories.json     (not specific businesses — categories by area)
├── inter_city.json         (connections to other packs)
├── weather_config.json     (NWS zone, Open-Meteo coordinates)
└── transit_config.json     (GTFS feed URLs for this city)
```

### Building a pack

```bash
python scripts/build_city_pack.py \
    --city "San Francisco" \
    --osm-extract sf-bay-area.osm.pbf \
    --transit-gtfs bart-gtfs.zip muni-gtfs.zip \
    --output data/cities/san_francisco/
```

This is a one-time, offline operation. It can take minutes to hours
depending on the metro size. The output is a small set of JSON files
(typically < 10MB per city) that the server loads at startup.

### Planned packs

| City | Priority | Notes |
|------|----------|-------|
| San Francisco | First (current world) | BART, Muni, fog, tech culture |
| Portland | Second (meatspace home) | MAX, bridges, neighborhoods, rain |
| New York | Future | Subway, boroughs, density |
| Amsterdam | Future (NL relocation) | Trams, canals, gezelligheid |

### V5 federation angle

Each city pack maps naturally to a steward node. Someone in Portland runs
the PDX node. The SFO-PDX inter-city corridor is shared infrastructure.
When a resident takes the Coast Starlight from SF to Portland, their session
transitions from one node's jurisdiction to another's.

## Implementation Order

### Phase 1: Seed the map (no live data yet)

1. Build a minimal San Francisco skeleton by hand:
   - 10-15 neighborhoods with adjacency
   - BART stations + lines
   - 20-30 landmarks/parks
   - Major street corridors
   - SFO-PDX corridor

2. Add `GET /api/world/map/{session_id}` endpoint to WorldWeaver

3. Feed map data to the slow loop as context — "Here's what you know about
   the city's geography"

4. Test: does the narrator produce more coherent geography when the slow
   loop has map context?

### Phase 2: Location expansion

5. Add `POST /api/world/map/expand` endpoint

6. Implement the grounding query pipeline:
   - Parse location name from action text
   - Check seed cache
   - If miss: geocode via Nominatim (cached permanently after first hit)
   - Create grounded node in fact graph
   - Return to narrator as context

7. Test with the explorer resident: do new locations get grounded correctly?
   Do they persist and become available to other residents?

### Phase 3: Live weather

8. Add weather ingester to the grounding daemon:
   - Poll NWS + Open-Meteo every 30-60 min
   - Transform into grounded_weather facts
   - Inject via `/api/world/grounding/inject`

9. Add `GET /api/world/pulse` endpoint

10. Feed weather to the narrator and scene card. Test: does "foggy today"
    show up in scenes? Do residents react to weather?

### Phase 4: Live transit

11. Add BART GTFS-rt ingester
12. Transform delays/disruptions into grounded_transit facts
13. Test: do residents experience transit delays? Does the explorer's
    route planning respond to disruptions?

### Phase 5: City pack tooling

14. Build `scripts/build_city_pack.py` for automated pack generation
15. Build Portland pack
16. Test inter-city travel: SFO → PDX via grounded corridor

### Phase 6: Events (optional, v2)

17. Add GDELT ingester
18. Transform structured events into world pressures
19. Test: do protests affect foot traffic? Do residents mention civic events?

## Non-Goals

- **Live business data.** No Yelp reviews, no Google Places details, no
  specific business hours. The world is grounded in geography, not commerce.
- **Street-level accuracy.** The map is neighborhood-and-corridor level, not
  turn-by-turn navigation. "Walk down Valencia" is grounded; "turn left at
  the third house past the blue mailbox" is narrator territory.
- **Real people.** Grounded geography, emergent characters. Never seed
  real individuals into the world. If a real business name appears, let it
  be narrator invention, not API truth.
- **Always-online dependency.** If every external API goes down, the world
  keeps running on its seed cache. Live data enriches; it never gates.

## Design Principles

1. **Seed expensive, serve cheap.** Build the skeleton once. Cache everything.
   Runtime external API calls should be < 20/hour total.

2. **Ground the bones, free the flesh.** Geography is real. People are emergent.
   Weather is live. Salsa verde is invented.

3. **The map is a character's knowledge, not God's.** Each resident knows
   the locations they've visited or heard about. The explorer knows more of
   the map than Mateo, who never leaves the taqueria.

4. **Stale is better than blocked.** If the weather cache is 2 hours old,
   use it. If Nominatim is down, let the narrator invent. Never block
   gameplay on an external service.

5. **Transform, don't mirror.** External data becomes world pressure, not
   content. A headline becomes foot traffic. A weather alert becomes fog
   on the windows. A transit delay becomes a crowded platform.

6. **Expansion is attention-driven.** New locations appear because someone
   went there. The map grows through curiosity, not census. The explorer
   widens the world. The doula populates it. The reducer remembers it.
