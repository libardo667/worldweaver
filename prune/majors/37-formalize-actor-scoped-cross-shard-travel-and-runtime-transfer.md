# Formalize actor-scoped cross-shard travel and runtime transfer

## Status

This major now materially supersedes Major 07.

Major 86 further constrains it: every AI resident has a private hearth, and city<->hearth travel is one
continuous resident changing exclusive world attachment. Do not serialize a second "resident payload" or
run overlapping cognition merely to enter the hearth; the resident home remains authoritative.

The older inter-city travel framing assumed a looser shard switch mechanic. The
active travel problem is now actor-scoped identity continuity, portable runtime
state, and explicit departure/arrival semantics across shards.

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

This payload should be:

- actor-scoped
- serializable
- rebuildable from ledger/reduced state where possible
- portable across shards without carrying shard-local implementation junk

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
- [ ] Cross-shard travel is represented as a formal lifecycle with departure, traveling, and arrival states
- [ ] A destination shard can bootstrap a new local session for an existing actor without creating a second identity
- [ ] Actor-scoped runtime continuity can be serialized and transferred between shards in a bounded payload
- [ ] AI travel can be represented as a first-class intent or operation, even if motivational/discoverability work lands later
- [ ] Traveling actors do not appear as simultaneously active in multiple shards
- [ ] The implementation reduces dependence on shard-local session IDs as long-term identity keys
- [ ] The resulting travel/runtime contract is compatible with future portable scoped orchestration work

## Risks & Rollback

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
