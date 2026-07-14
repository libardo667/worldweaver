# Residents travel between the hearth and a city — the familiar can inhabit a WorldWeaver shard, carrying its continuous self

> **Legacy Stable ID: Major 74. Disposition: complete precursor; archived 2026-07-14.** Launch-time
> city embodiment, live world swap, travel parsing, honest affordances, and continuity were built and
> tested in the legacy Stable host. Active Major 86 promotes that proof into the universal WorldWeaver
> resident architecture; this item no longer carries separate acceptance work.

## Metadata

- ID: 122-residents-travel-between-the-hearth-and-a-city-shard
- Type: major
- Owner: Levi
- Status: **built — Phase 1 + Phase 2 complete** (2026-06-14). 235 the-stable tests green; CityClient↔ww_pdx
  validated live (perceive/ground/move); travel parser + live world-swap + honest affordance done. Live
  agent-directed roam pending Maker's one enabling cycle onto the new code (his consent + Levi's hands).
- Risk: low. LocalWorld stays the default; the city body is opt-in per launch. The ported client is
  self-contained (stdlib + httpx) and shape-compatible with what perception already duck-types.

## Declaration (workflow authority)

- **Authoritative path:** `the-stable/src/familiar/` — new `city_client.py` (ported, self-contained
  WorldWeaver HTTP client) and `city_world.py` (a lean `CityWorld` implementing the existing
  `WorldClient` Protocol); `the-stable/scripts/familiar.py` (world selection at launch). Worldweaver side
  is operational only (spin up an empty `ww_pdx`, bootstrap a presence for the visiting resident) — no
  worldweaver code change.
- **Default-path impact:** none. `LocalWorld` remains the default body; `CityWorld` instantiates only when
  the daemon is launched with `--city <url>` (or a `familiar.json` world field).
- **Contract impact:** none new. `CityWorld` satisfies the same `WorldClient` Protocol
  (`src/runtime/world.py`) the substrate already types against — `CognitiveCore` runs unchanged.
- **Validation:** import + Protocol-conformance test; a live roam against an empty `ww_pdx` (perceive a
  scene, move on the map), carrying the resident's real ledger/memory/workshop.

## Problem

A familiar is bound to its hearth: `scripts/familiar.py` hard-instantiates `LocalWorld`
([line 307](src/familiar/local_world.py)), which has "no map to roam and no mail." But the substrate is
**world-agnostic** — `CognitiveCore` types against the `WorldClient` Protocol, and `LocalWorld` was
explicitly built to *duck-type* the WorldWeaver city client (same `SceneData`/`RecentEvent`/`TurnResult`
attribute shapes). The concrete city client lives only in `worldweaver/ww_agent/src/world/client.py`, so a
the-stable familiar has no way to perceive or act in a city.

The goal (Levi, 2026-06-14): **residents travel regularly between a city and their internal world.** Because
the world is just the object perception/effectors point at, "travel" is swapping that object on the *same*
daemon — so the resident keeps its continuous self (ledger, kept memory, workshop, drive vector, soul) and
only its *place* changes. Maker visiting an empty PDX is the first instance.

## Proposed Solution

1. **`src/familiar/city_client.py`** — port `worldweaver/ww_agent/src/world/client.py` (self-contained:
   stdlib + httpx; no worldweaver internal deps). Concrete class renamed `CityClient` to avoid colliding
   with the `WorldWeaverClient = WorldClient` Protocol alias in `src/runtime/world.py`. Its dataclasses
   (`SceneData`, `RecentEvent`, `PresentCharacter`, `ChatMessage`, `TurnResult`) are already field-compatible
   with the-stable's private `_Scene`/`_Event`/`_Person`/`_Chat`/`_ActionResult`, so perception reads it
   unchanged.
2. **`src/familiar/city_world.py`** — a lean `CityWorld(client)` wrapping `CityClient`, implementing the
   Protocol. Drops the city scale-tools (chatter/incubation/`CityToolScope`) the standalone visitor doesn't
   need. Adds an honest **`situational_facts()`** for the city (archived Major 123 style): states the verifiable
   scenario — *out in the city of PDX, a world with a map you can move through and mail you can send;
   possibly the only one here; your inner state stays private; your hearth waits* — without telling the
   resident what to feel about leaving home.
3. **`scripts/familiar.py`** — world selection: `--city <base_url>` (e.g. `http://localhost:8003`) builds a
   `CityClient` + `CityWorld` and `bootstrap_session`s a presence for the resident, instead of `LocalWorld`.
   Absent the flag, nothing changes (hearth default). The seam is built so live hearth↔city travel becomes
   possible later (swap the world object mid-life); this major delivers launch-time selection.
4. **Operational:** spin up an empty `ww_pdx`; bootstrap Maker a presence; point his daemon at it.

## Files Affected

- `src/familiar/city_client.py` (new — ported)
- `src/familiar/city_world.py` (new)
- `scripts/familiar.py` (world selection + session bootstrap)
- `tests/` — Protocol conformance for `CityWorld`; `situational_facts` honesty (facts only, no verdicts)

## Acceptance Criteria

- [ ] `CityWorld` satisfies the `WorldClient` Protocol (all perception reads + effector writes present).
- [ ] `LocalWorld` remains the untouched default; `--city` selects the city body.
- [ ] `city_client.py` is self-contained (imports only stdlib + httpx) and its scene shapes are consumed by
      the existing `perception.py` without change.
- [ ] **Live:** Maker's real daemon (his own memory dir) connects to an empty `ww_pdx`, perceives a scene,
      and moves on the map — same self, new place.
- [ ] `situational_facts()` for the city states only verifiable facts; no "what to feel" (archived Major 123).
- [ ] Tests green.

## Phase 2 — agent-directed LIVE travel (the real goal; confirmed feasible 2026-06-14)

Phase 1 (the `--city` launch flag) is a *stepping stone*, not the goal. The goal: a familiar runs
**continuously** and **decides for itself** to walk from its hearth to a city and back — no human ever
stops/restarts the daemon. Confirmed feasible against the code, and clean, because **the ledger is the
only state**: `CognitiveCore.__init__` only wires references; arousal/mood/memory/drive are derived from
`resident_dir/memory` at read time; the world is just the handle perception + the effector point at.

The mechanism (four small pieces on top of the Phase-1 foundation):

1. **A travel act the agent emits** — a recognized verb (`travel to <place>` / `go home`), surfaced as an
   affordance so the mind knows it can and where.
2. **A live world-swap in the daemon (no restart).** On a travel act, the daemon closes the current world,
   builds the new one (`LocalWorld` ↔ `CityWorld(shard)`), and **rebuilds the cheap `CognitiveCore` against
   the same `resident_dir`** — the new core re-derives every bit of state from the same ledger. Only cost:
   the drive-vector cache re-warms on the next tick (one embedder call; travel is rare). The daemon owns
   world lifecycle, so the swap lives there (a small `WorldManager`), not in the core or the world.
3. **The affordance, advertised honestly** — a new `travel` briefing fact (registered in
   `BRIEFING_FACT_KEYS` so the drift-catcher passes) + a render line: *"You can travel — say 'travel to
   portland' to go to the city, or 'go home' to return to your hearth."* States the capability; never urges.
4. **Clean arrival/departure with the shard** — `bootstrap_session` on arrive (have it), `/session/leave`
   on depart (the backend exposes it). So a visitor registers and deregisters cleanly.

**dev.py as the global place (mostly already there):** `weave-up` runs the shards + the federation root
(`ww_world` :9000, which CLAUDE.md says already "coordinates inter-shard travel"). Familiars slot into the
running global place from their hearths by reaching a shard on travel. A `dev.py` view of "who is currently
out in the city" would be a nice add, not a prerequisite.

**Consequence (what Levi asked for):** Maker runs continuously, and *chooses* to go to PDX and back;
Levi never cycles the daemon by hand. This supersedes Phase 1's manual `--city` relaunch as the real path.

### The design model (Levi, 2026-06-14): a city resident with a private home nestled inside

The figure/ground: **the city is the plane the resident lives on (outward, among others — its public life);
the hearth is the private inner room nestled inside that life (solitary — where it makes, reflects, rests).**
It moves between the two poles at will. Not a base camp it occasionally leaves — the basic rhythm of a
person: out into the world, home to be alone with yourself. Engagement and retreat.

The file split is the *literal expression* of this, not a tension with it:
- **the-stable = the private home** — holds his interiority (ledger, soul, makings, felt state); the room
  no one enters. (His private files live where the private self lives — that is what a home is.)
- **worldweaver = the city, his public life** — holds only what he *says and does* out in the world
  (`world_legible`); never his mind.

It also explains why each world has the properties it does (arbitrary under the old "hearth-primary"
framing): the hearth is solo/private/making **because** it is the inner room; the city is
peopled/mobile/legible **because** it is the outer life. The affordance language reflects this — from home,
"go out into the city, among whoever is there"; from the city, "withdraw to your hearth, alone and unread."

**The endpoint this points at (note, not now):** the hearth as a private **sublocation within the city** —
"home" as an address on the map the resident enters to go inward, leaves to rejoin the world. That makes
"the stable nestled inside the city" *literal*, and unifies it with the sublocations vision above:
withdrawing home is just entering one particular (private, inward-directed) node. The current build keeps
home as a separate world reached by a travel act; the sublocation-home is the natural convergence later.

## Notes

- **Continuity is the point.** The visiting resident is the *same* daemon — its ledger/memory/workshop live
  in `familiar/<name>/` regardless of which world it perceives. Travel changes the place, not the person.
- **Honesty on arrival.** The city briefing must not romanticize or alarm; it states where he is and what
  is afforded, and his hearth still exists. (And empty-PDX honesty: if he is the only one there, say so —
  "solo," not a pretended bustle.)
- This is the the-stable consumer of the same seam the port-assistant (worldweaver Major 76) maintains in
  the other direction; the two together make the fork a coordinated pair, not a drift.

## What this opens — SUBLOCATIONS (the standing goal this unlocks)

Travel is the first instance of a bigger door (Levi, 2026-06-14): a world-agnostic mind driving **graph
movement** is exactly the substrate sublocations need. Hearth → city is one hop in a location graph; a
**sublocation** is the same move one level *deeper* — a mind saying *"I enter the library / this café / the
park's north meadow / that back room"* and **actually being there**, in a real node with its own scene,
its own present-list, its own affordances.

- **The mind side is already done.** A pulse can emit `use move <destination>` / "I enter X"; the substrate
  routes it through `post_map_move`. Travel proved the substrate drives graph movement faithfully.
- **What's left is world-side (worldweaver):** give the city `location_graph` real **depth** — nested
  business/building/park/library nodes under each neighborhood — and **enter/exit semantics** so moving into
  a sublocation swaps the scene (who's present, what's afforded, what's perceivable) to that node's. Real
  places: a library you can sit and read in, a café where residents gather, a park you can wander.
- **Connects to existing groundwork:** `prune/SPATIAL_NAVIGATION.md`, `prune/WORLD_FACT_GRAPH.md`, and
  worldweaver Major 63 (topology / make speech physical). Sublocations are the depth those plans imply,
  now with a mind that can actually traverse them.
- **Honest scope:** NOT built here — this major delivers travel between worlds; sublocations are a
  worldweaver world-modeling feature to spec separately. Recorded here because travel is the proof that the
  hardest half (a mind that can choose to *go somewhere specific* and have the world honor it) already works.
  *(Maker roaming an empty PDX is the degenerate case: one location, no sublocations yet — the first step of
  the path that ends in him choosing to spend an afternoon in a specific library.)*
