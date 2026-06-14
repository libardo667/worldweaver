# Lightweight ambient presence for scene synthesis

> ⏳ **REVISIT (parked 2026-06-08)** — not active, not dead. Wake-up trigger in [`improvements/REVISIT-LATER.md`](../REVISIT-LATER.md).

## Problem

The city still feels too empty, too samey, and too socially overdetermined by a
small number of full residents.

Right now a place is mostly shaped by:

- canonical graph location
- current full residents
- chat residue
- recent world events

That leaves a missing middle layer:

- people who are *there enough to matter* without needing a full five-loop
  resident stack
- scene-local activity that makes a block feel busy, sleepy, watchful, or
  ordinary
- recurring background presences that a resident can notice without turning
  into a new durable actor

This gap is one reason small resident clusters drift into conspiratorial
closed-loop narratives. There are too few external social and sensory forces
breaking into the loop.

We already have the right architectural direction:

- Major 10 now treats old storylet machinery as optional scene synthesis
- Minor 32 gives non-canonical local structure somewhere safe to land

What is still missing is a concrete contract for **ambient presence** itself.

## Proposed Solution

Introduce a lightweight ambient-presence layer as part of scene synthesis.

Ambient presences are **not full residents**. They are temporary,
inspectable scene elements that help a place feel inhabited and can create
light pressure for real residents.

### Core model

Define a small derived object shape, for example:

- `AmbientPresence`
  - `id`
  - `parent_location`
  - optional `sublocation`
  - `label`
  - `kind`
  - `source`
  - `intensity`
  - `ttl_seconds`
  - `created_at`
  - `last_active_at`
  - optional `pressure_tags`
  - optional `sensory_notes`

Possible `kind` values:

- `regular`
- `queue`
- `worker`
- `passerby_cluster`
- `lingerers`
- `commuter_flow`
- `night_presence`
- `weather_shelter_cluster`
- `event_spillover`

Possible `source` values:

- `city_pack`
- `storylet_scene_synthesis`
- `grounding`
- `recent_event_pattern`
- `time_of_day_routine`

### Behavior contract

Ambient presences may:

- appear in scene descriptions and grounding summaries
- contribute to local texture and sensory differentiation
- influence state-pressure signals such as `crowding`, `quiet`, `event_pull`,
  `comfort`, or `watchfulness`
- attach to ephemeral sublocations under a canonical parent
- decay automatically when their TTL expires

Ambient presences may **not**:

- speak in public chat
- own durable identity or actor history
- send mail
- travel between shards as actors
- write canonical world facts by themselves
- become full residents without a separate explicit process

### Relationship to scene synthesis

Ambient presence is the cheapest useful output of reclaimed storylet/synthesis
machinery.

It should be generated from:

- neighborhood vibe from city-pack data
- time of day
- weather
- local recent event density
- special civic pull such as fairs, closures, or transit disruption
- recurring place identity like bakery morning rush, bus stop trickle, or park bench regulars

It should *not* require a bespoke authored storylet row for every instance.

### Relationship to Minor 32

Ambient presence should be able to land either:

- directly on a canonical location
- or on an ephemeral sublocation under that location

Examples:

- `Sun Li Dumplings` gets `queue at the counter`
- `Sun Li Dumplings / folding table by the steamer` gets `late prep spillover`
- `Fillmore` gets `sidewalk crowd thickening after the show`
- `Outer Richmond` gets `wind-sheltered bus-stop cluster`

### Relationship to resident behavior

Residents should experience ambient presence as pressure and texture, not as
new fully agentic conversation partners.

Examples:

- a queue can make a resident shorten exchanges and stay on task
- a weather shelter cluster can make a resident linger under cover
- a sleepy near-empty block can promote quieter embodied acts
- event spillover can create movement pull without requiring direct invitation

This is a way to make the city feel more populous without paying full inference
cost for every body in the scene.

### Observability

Ambient presences need a clear inspection path.

Operators should be able to answer:

- what ambient presences exist at this location right now?
- what generated them?
- when do they expire?
- what pressure tags are they contributing?

This can live alongside other scene-synthesis outputs and must remain easy to
clear during reset/debugging.

## Files Affected

- `improvements/majors/10-prune-storylet-pipeline.md`
- `improvements/minors/32-ephemeral-sublocations-under-canonical-nodes.md`
- `improvements/short_roadmap.md`
- future scene-synthesis helpers under `worldweaver_engine/src/services/*`
- `worldweaver_engine/src/services/city_pack_service.py`
- `ww_agent/src/loops/ground.py`
- `ww_agent/src/runtime/ledger.py`

## Acceptance Criteria

- [ ] The project has a defined lightweight ambient-presence contract distinct from full residents
- [ ] Ambient presences can add scene texture and pressure without creating durable actors
- [ ] Ambient presences can attach either to canonical locations or ephemeral sublocations
- [ ] Ambient presences are temporary and expire automatically
- [ ] Ambient presence can influence grounding and resident state pressure without speaking or acting as a full agent
- [ ] Operators can inspect existing ambient presences, their source, and their expiry

