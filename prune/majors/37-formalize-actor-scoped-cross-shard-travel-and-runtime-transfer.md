# Formalize actor-scoped cross-shard travel and runtime transfer

## Status

This major now materially supersedes Major 07.

Major 86 further constrains it: every AI resident has a private hearth, and city<->hearth travel is one
continuous resident changing exclusive world attachment. Do not serialize a second "resident payload" or
run overlapping cognition merely to enter the hearth; the resident home remains authoritative.

The older inter-city travel framing assumed a looser shard switch mechanic. The
active travel problem is now actor-scoped identity continuity, portable runtime
state, and explicit departure/arrival semantics across shards.

Federation is a grounding constraint for this work. A city node owns its database, city pack,
residents, and local facts. The federation root may provide shared identity, discovery, health,
mail, and transfer coordination, but it must not become the owner of city state or a master list
that decides which cities are allowed to exist. Travel joins independently operated nodes; it
does not turn them into branches of one central server.

Local-first has an operational meaning here: a node must continue running its local world when its
federation root or a peer is unavailable. Cross-node discovery, login hydration, mail, or travel may
be temporarily unavailable and should say so plainly. Loss of the coordinator must not erase local
identity projections, stop resident life, or make local facts unreadable.

## Problem

Cross-shard movement is currently only partially formalized.

Today:

- humans already have a durable `actor_id` in the federation and local shard
  projections
- AI residents have a mix of `resident_id`, local directory identity, and
  session identity
- `session_id` still does too much identity work in map occupancy, presence, and
  shard-to-shard continuity
- shard switching for humans can leave behind stale local sessions and ghost
  occupancy
- inter-city travel exists more as UI/context switching than as one actor
  departing, traveling, and arriving with portable continuity

This creates several concrete problems:

- map occupancy and roster surfaces can disagree because they dedupe different
  identity layers
- leaving one shard and entering another can leave ghost sessions behind
- humans and AI do not yet use one fully shared travel contract
- runtime continuity ("soul stuff", current concerns, ledger-derived state,
  correspondence, travel intent) is not yet formalized as actor-scoped payload
  that can move between shards
- Major 35 is deepening resident continuity, but cross-shard movement still
  treats sessions as if they were identities

Without a first-class travel operation, the federation remains a registry more
than a world. Movement between cities becomes re-instantiation instead of one
actor crossing one topology.

This major updates and materially supersedes the implementation assumptions in
Major 07. Inter-city travel should no longer be treated as a single-DB city
context switch. It should be formalized as actor-scoped transfer between shard
runtime scopes.

## Proposed Solution

Treat all persons in WorldWeaver, human and AI, as durable actors whose shard
membership is temporary and whose runtime sessions are local incarnations.

Travel should become a first-class actor transfer operation:

- `actor_id` is the canonical identity
- `session_id` is a shard-local runtime handle only
- departure removes or retires the source-shard incarnation
- arrival creates or rehydrates the destination-shard incarnation
- actor-scoped continuity moves with the actor

For a resident entering its hearth, "moves" means the same daemon/core owner detaches from its public
session and attaches to its private actor-scoped world. City-to-city rehosting may still require a portable
payload, but hearth entry must not be implemented as migration between competing resident copies.

This major depends directly on:

- Major 20 for federation-wide actor identity
- Major 35 for portable runtime ledger/projection/fact continuity

It should inform the sequencing of Major 25 because unified scoped runtime
architecture will make actor transfer cleaner and more portable.

### Phase 1 - Define the actor travel contract

Introduce one cross-shard travel operation shared by humans and AI.

Canonical model:

- actor identity: `actor_id`
- source runtime: one shard-local session bound to that actor
- destination runtime: a newly booted or rehydrated shard-local session bound to
  the same actor
- travel state: `active -> traveling -> active`

The travel contract should explicitly carry:

- `actor_id`
- `actor_type`
- `source_shard`
- `destination_shard`
- `departure_hub`
- `arrival_hub`
- `departed_at`
- `arrive_after` or `arrive_at`
- portable runtime payload reference
- reason / trigger metadata

This is the core state machine both human and AI travel will use.

### Phase 2 - Make actor identity truly first-class for AI as well

Finish the identity parity that Major 20 points toward.

- every AI resident gets a durable `actor_id`
- doula mints or resolves actor identity before scaffolding/boot
- resident-local `resident_id` becomes one projection of `actor_id`, not a
  competing identity layer
- map occupancy, presence, federation pulse, doula logs, travel logs, and DMs
  should all be able to resolve the same actor

For immediate bug reduction:

- occupancy and roster dedupe should key off `actor_id` where present
- agent fallback dedupe can temporarily use durable resident identity when full
  actor migration is incomplete

### Phase 3 - Formal departure and arrival operations

Add explicit travel lifecycle endpoints and runtime behavior.

On departure:

1. validate that the actor may depart from the current shard/hub
2. record a travel event at shard and federation level
3. mark the actor `traveling`
4. remove or retire the source-shard session from occupancy/presence
5. persist portable actor runtime payload for transfer

On arrival:

1. resolve actor identity in destination shard
2. bootstrap a new local session for the same `actor_id`
3. hydrate runtime state from transferred actor payload
4. place the actor at the arrival hub
5. mark the actor `active`
6. emit arrival events and presence updates

This must apply to:

- human-initiated inter-city travel
- future AI travel decisions
- operator/dev travel moves where appropriate

### Phase 4 - Define the portable runtime payload

Travel should move continuity, not just a name and destination.

The first transfer payload should be deliberately bounded and should evolve
directly out of Major 35.

Initial actor-scoped portable payload:

- reduced runtime state
- current concerns
- active social threads
- subjective facts
- pending correspondence
- pending research
- travel-relevant memory projection
- optional local identity artifacts such as soul/voice summaries

Do not treat the local world as actor luggage. Major 125's stoops and their live contents remain owned by
the city node. A later object-carrying contract may include items an actor deliberately takes, but travel
must not copy a whole stoop, local trace field, or private workshop merely because the actor changes cities.

This payload should be:

- actor-scoped
- serializable
- rebuildable from ledger/reduced state where possible
- portable across shards without carrying shard-local implementation junk
- held only as long as needed for handoff; the coordinator must not quietly become the permanent owner
  of every resident's private runtime state

Longer term, the runtime payload should become a portable scoped-state bundle
rather than a handpicked set of files.

### Phase 5 - Travel hubs and discoverability

Travel should become an explicit world mechanic rather than hidden shard admin.

Humans:

- can only initiate cross-shard travel from recognized travel hubs or equivalent
  UI affordances
- see available routes, destinations, and travel conditions

AI:

- can learn that travel hubs exist
- can stage travel intents just as they stage move/chat/mail intents
- can reason about travel as a world action rather than an operator trick

The runtime architecture should come first. AI discoverability and motivation can
follow once travel is a real operation.

#### City packs, possible routes, and live nodes

`worldweaver_engine/scripts/build_city_pack.py` already has the right basic boundary. A city is
defined by a local config and built into a portable pack; adding a city does not require adding
city-specific Python. Keep that model.

Do not replace it with a repository-owned global city catalog. These are three separate things:

- a city pack describes one place;
- that pack's `inter_city.json` describes physically possible routes, including routes to places
  that may not currently have a live WorldWeaver node;
- the live federation registry says which independently operated `shard_id` currently hosts which
  `city_id`, at what URL, and whether it is reachable.

A later route resolver should join local route possibilities with live registry entries. The UI
can then say honestly that a destination is available, offline, or not currently hosted without
making the federation root the source of geographic truth.

As of 2026-07-17, `SHARD_ID` is explicit node configuration and `CITY_ID` remains the hosted pack.
Legacy nodes fall back to `CITY_ID` as their old registry key. Federation pulses now report that
node identity and prefer the actor already bound to the session over a potentially stale identity
file. This settles an identity prerequisite; it does not yet implement transfer.

### Phase 6 - Unify occupancy, presence, and roster semantics

All presence surfaces should answer the same question:

"Which actors are currently instantiated in this shard and where?"

That means:

- map occupancy dedupes by actor identity
- shard presence panels dedupe by actor identity
- stale sessions without the current actor incarnation do not appear as live
  people on the map
- traveling actors do not appear as simultaneously present in multiple shards

This should eliminate the current class of ghost-session bugs where one actor
appears in multiple neighborhoods after shard switching or partial restart
conditions.

### Phase 7 - Align runtime architecture with portable scoped orchestration

This major should be implemented in a way that supports the medium-term
35/25 direction:

- one ontology
- one reducer/query family
- many scopes

Residents should not become literal Docker stacks immediately. But travel should
be designed as if actor-scoped runtime continuity might later be:

- rehosted
- moved across workers
- managed by a broader scheduler

That keeps the door open for future orchestration layers, including Kubernetes,
without prematurely turning every actor into infrastructure overhead.

## Files Affected

- `prune/majors/07-inter-city-travel.md`
- `prune/majors/20-federation-wide-actor-identity.md`
- `prune/majors/25-collapse-worldweaver-engine-and-ww-agent-into-ww-engine.md`
- `prune/majors/35-deepen-the-fractal-architecture-with-resident-ledgers-and-subjective-fact-graphs.md`
- `worldweaver_engine/src/models/__init__.py`
- `worldweaver_engine/src/api/game/state.py`
- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/src/api/federation/routes.py`
- `worldweaver_engine/src/services/federation_identity.py`
- `worldweaver_engine/src/services/federation_pulse.py`
- `worldweaver_engine/src/services/session_service.py`
- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/api/wwClient.ts`
- `worldweaver_engine/client/src/components/LocationMap.tsx`
- `ww_agent/src/resident.py`
- `ww_agent/src/runtime/ledger.py`
- `ww_agent/src/runtime/mirror.py`
- `ww_agent/src/loops/slow.py`
- `ww_agent/src/loops/fast.py`
- future actor-travel / transfer service modules in backend and agent runtime

## Acceptance Criteria

- [ ] Humans and AI residents both have one durable `actor_id` that survives shard changes
- [ ] Map occupancy and shard presence dedupe by actor identity rather than raw session identity
- [ ] Leaving one shard and arriving in another does not leave live ghost occupancy behind in the origin shard
- [x] Cross-shard travel is represented as a formal lifecycle with departure, traveling, and arrival states
- [ ] A destination shard can bootstrap a new local session for an existing actor without creating a second identity
- [ ] Actor-scoped runtime continuity can be serialized and transferred between shards in a bounded payload
- [ ] AI travel can be represented as a first-class intent or operation, even if motivational/discoverability work lands later
- [ ] Traveling actors do not appear as simultaneously active in multiple shards
- [ ] The implementation reduces dependence on shard-local session IDs as long-term identity keys
- [ ] The resulting travel/runtime contract is compatible with future portable scoped orchestration work
- [ ] City discovery preserves the difference between portable city packs, possible routes, and live independently operated nodes
- [ ] No central service owns city state or acts as an approval gate for which cities may join the commons
- [ ] A city node remains locally usable during a federation outage, with unavailable cross-node features reported honestly
- [ ] Transfer coordination does not turn the federation root into the permanent store for resident runtime payloads

## Risks & Rollback

### Build log — 2026-07-17

- Separated configured node identity (`SHARD_ID`) from hosted city-pack identity (`CITY_ID`) across
  shard creation, registration, reset, status, and federation pulses.
- Kept a legacy `CITY_ID` fallback so existing nodes do not silently change their registry identity.
- Made resident pulses prefer the actor ID already bound to the live session over a stale local file.
- Added an operator-facing `--shard-id` option and a test proving one Portland pack can be hosted by a
  differently named community node.
- Reviewed this boundary against `prune/VISION.md` and Major 80's commons thesis.
- Full repository check passed: 479 engine tests and 311 agent tests, with 1 agent test skipped.

This is identity and discovery groundwork only. Formal departure, transfer, and arrival are still open.
The existing client dropdown is also labeled as a node change rather than travel: it clears local auth and
session state, so presenting it as city travel would promise continuity that it does not yet provide.

The first read-only destination contract is now present at `GET /api/world/travel/destinations`. It reads
possible routes from the node's own city pack and joins them to every matching city node in the live
federation registry. A route is reported as available, offline, unhosted, or unknown. Registry failure
leaves the local route list intact and returns unknown availability. The endpoint does not move an actor.

The federation root now records each trip under a caller-supplied, stable `travel_id` and explicit
`departing -> traveling -> arrived` states. Starting, departing, and arriving are idempotent. The source
node is the only node allowed by the contract to confirm departure, and the destination is the only node
allowed to confirm arrival. The actor remains attributed to the source while traveling and changes its
current node only after arrival is confirmed. Existing pulse-based travel records are kept compatible,
but the explicit endpoints are the new authority.

This is still coordination, not end-to-end transfer. City nodes do not yet call the contract, source
session retirement is not yet joined to departure, destination bootstrap is not yet joined to arrival,
and no private runtime payload moves. Node ownership is currently enforced at the API-contract level on
top of the federation's shared token; stronger per-node credentials remain future hardening.

- This touches identity, presence, occupancy, map semantics, session lifecycle,
  federation state, and resident continuity at once. It should not be shipped as
  a flag-day rewrite.
- If actor identity is only partially adopted, dedupe behavior can become more
  confusing rather than less. Human and AI identity migration should be staged
  explicitly.
- Portable runtime payloads can accidentally include shard-local or stale state
  if the transfer boundary is not clearly defined. Keep the first payload small
  and reducer-derived.
- Travel hubs and AI travel intent should not block the underlying travel
  contract. Build the operation first; add richer discoverability and motivation
  after the transport is real.
- Rollback path: keep legacy shard-local session travel behavior available behind
  a feature flag during rollout, retain compatibility dedupe paths for old
  resident identities, and avoid deleting legacy travel/session plumbing until
  actor-scoped arrival/departure has been validated end to end.
