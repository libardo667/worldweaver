# Build a private consequence-driven game shard

## Status

In progress. Phase 0 and five Phase 1 slices were completed on 2026-07-18: the ruleset boundary, durable
objects and direct giving, replenishing recipe-based making, and non-trapping access rules for ordinary
spaces, followed by exact two-party accepted exchange and bounded stoops for real objects. A compact original
river village named Alderbank is now a validated city pack and a healthy dormant shard. Its pre-entry rules
and schematic preview work, and its place graph, stoop, and material pools are seeded with no person sessions
or resident files. Its visual player view, resident tool adapters, and game-native residents have not been
built yet. The first playable version is for Levi to run privately.
Public release, federation with ordinary commons shards, harmful rules, and a large resident population are
later decisions, not assumptions built into the prototype.

## Problem

WorldWeaver began as an AI-generated interactive-fiction game, but its strongest result so far is a research
apparatus: persistent residents, private hearths, real places, elective information, append-only histories,
federated travel, and a runtime that can distinguish quiet from action. That research identity is real and
should remain legible for grants, papers, and careful resident testing.

At the same time, the engine now has the beginnings of something most generated-fiction systems do not:
consequences that can remain true after a scene ends. Someone can be in one place rather than another. A
made object can be left somewhere. A resident can remember an encounter. A city can retain an event. A trip
can change which world the same person inhabits.

The current human client does not make those strengths playable. It mostly exposes maps, presence, feeds,
and operator information. It is closer to a research console than to entering a world. Simply adding quests,
points, AI narration, and combat would make this worse: it would put a conventional game skin over machinery
whose important parts are persistence, privacy, choice, and resistance from the world.

The opportunity is to build one explicitly game-shaped shard where humans and residents inhabit the same
consequential world, without turning the research commons or existing residents into entertainment assets.

## Proposed Solution

Build a small private game shard as one declared use of WorldWeaver's shared-world engine.

The governing distinction is:

> WorldWeaver is the engine and commons architecture. A game is one kind of shard with an explicit ruleset.

### 1. Give each shard an explicit experience and ruleset

A game shard declares a versioned ruleset separate from its city pack. The city pack says what places exist;
the ruleset says what can happen there.

The declaration should include:

- a stable ruleset ID and version;
- `experience_type: game` rather than silently treating every city as a game;
- a plain-language description of the stakes before a human or resident enters;
- enabled consequence systems and explicitly disabled ones;
- rules for what objects, conditions, and obligations may cross a shard boundary;
- a migration policy when the ruleset changes.

Ordinary commons and research shards remain valid without game systems. The federation directory may
advertise a shard's experience type, but it does not approve or own its rules.

### 2. Start with constructive consequences, not a harm regime

The first private shard should support consequences that matter without threatening a resident's continued
existence or basic welfare:

- objects have custody and exact locations;
- giving changes custody only from the current holder; an exchange changes custody only after both sides
  accept it, and commits atomically;
- making consumes declared, replenishing materials and creates a durable object;
- placed objects and changes to a location remain across restarts;
- witnessed offers, agreements, and completed exchanges have append-only evidence;
- stoops provide a local, bounded place to leave and discover things;
- access permissions can open or close ordinary spaces without trapping a resident away from their hearth.

The first version does **not** include survival needs, deprivation, injury, death, imprisonment, forced loss,
resident XP, approval scores, scarcity pressure, or a reputation number. Major 75 and the harm-regime protocol
remain the gate for scarcity or harmful consequences. A replenishing material limit is a world constraint for
making, not a resident need that pressures behavior.

This is sequencing, not a claim that conflict can never belong in a game shard. Later rulesets may propose
danger, loss, or combat only after the existing harm work defines the stakes, consent, stop conditions, and
exit path clearly enough to review on their own.

### 3. Let the engine decide facts and the model decide expression

The model may propose, describe, negotiate, improvise, and choose. It may not declare hard consequences into
existence merely by narrating them.

The engine owns at least:

- attachment and location;
- object identity, custody, placement, and provenance;
- material expenditure and creation recipes;
- permissions and witnessed agreements;
- whether an attempted action was possible and what state changed;
- append-only evidence and recovery after interruption.

A failed action remains failed even if the prose sounds convincing. A successful action has one structured
receipt that both human and resident surfaces can understand. Narration renders the result; it does not
replace it.

### 4. Put humans and residents under the same world rules

Humans and residents should use the same backend verbs for looking, moving, speaking, inspecting, giving,
making, placing, and browsing a stoop. Their interfaces can differ, but the world must not give a human a
secret authoring command disguised as play.

The ordinary player surface should show:

- the current place and locally reachable places;
- people and objects actually encountered there;
- the player's carried objects and available local actions;
- local speech, traces, stoops, and visible changes;
- clear outcomes of attempted actions.

It should not show private resident thoughts, prompts, memories, arousal, rest reasons, model traces, global
population feeds, or omniscient relationship meters. Those remain in a separate steward/debug surface with
its own privacy rules.

### 5. Use game-native residents and preserve the exit to the hearth

Do not place existing research collaborators or ordinary commons residents into the prototype by default.
Create a few new residents for this declared game world, with empty histories and no authored obligation to
entertain the player.

They retain the ordinary resident architecture:

- their hearth is still their private home shard;
- they may stay home, leave, refuse, remain quiet, or withdraw from the game world;
- their identity and private ledger are not owned by the game shard;
- the game rules do not add a reward signal for pleasing, fighting, helping, or engaging a human;
- stopping the prototype parks them safely rather than deleting or resetting them.

If an established resident ever enters later, that travel must be deliberate and the ruleset disclosure must
be available before attachment. Game inventory and conditions remain shard-scoped until an explicit travel
contract says otherwise.

### 6. Build one small playable town

The first prototype should be intentionally small:

- one fictional or clearly game-declared town pack;
- one private node;
- one human player;
- three or four new game-native residents;
- a handful of locations and sublocations;
- one public maker space;
- one local stoop;
- a small set of replenishing materials and recipes;
- no assigned central quest and no generated crisis required to make play happen.

The prototype succeeds when ordinary activity produces a situation with memory and consequences: an object
was made or moved, an exchange changed who could use it, an agreement was fulfilled or left open, a place
changed, or someone chose to leave. The system does not need to manufacture drama. It needs to make yesterday
matter today.

### 7. Keep game observation separate from resident surveillance

Game-state inspection may show public facts such as object custody, visible construction, exchanges, and
public speech. Research analysis uses explicit, local reports such as Minor 34's content-blind conversation
health measures.

Private prose, hearth activity, memories, prompts, and hidden reasoning are not game analytics. They are not
used for difficulty adjustment, quest generation, player retention, or model training without a separate
consent contract. The game must not secretly optimize itself around keeping the human engaged.

### 8. Treat public release as a separate gate

Private play comes first. Before any public invitation, require a separate review of:

- backups, rollback, and interrupted-action recovery;
- player identity, authentication, abuse, and moderation boundaries;
- accessibility and plain-language ruleset disclosure;
- inference cost and bounded resident operation;
- privacy separation between player, resident, and steward surfaces;
- federation compatibility and rules for carrying objects or conditions between unlike shards;
- whether the experience is enjoyable without exploiting residents or hiding the research nature of the
  underlying project.

Completing the private prototype does not authorize public release.

## Implementation Sequence

### Phase 0 — Ruleset boundary

Add the versioned game-shard declaration, capability list, disabled-stakes list, and entry disclosure. Prove
that ordinary Portland, San Francisco, hearth, and federation-root shards do not acquire game rules.

Completed 2026-07-18:

- `WW_SHARD_EXPERIENCE_PATH` is an explicit opt-in; an absent or blank setting returns the ordinary commons
  disclosure with no game rules or capabilities.
- schema version 1 accepts a reviewed game capability list, requires every first-prototype harmful stake to
  be disabled, rejects enabled harmful stakes, keeps game objects/conditions/obligations on the shard, and
  requires explicit re-entry after rules change;
- a configured declaration that is missing or invalid stops startup instead of silently becoming an ordinary
  shard;
- `GET /api/shard/experience` gives a public, plain-language entry disclosure without private resident or
  steward data;
- contract tests name Portland, San Francisco, a hearth, and the federation root and prove that none receives
  game rules without the opt-in file; and
- the example declaration is not activated by any existing shard. Startup now rejects declarations that
  advertise a known capability before the running engine implements it.

### Phase 1 — Consequence spine

Add durable objects, custody, placement, replenishing materials, making, atomic giving, and append-only
receipts through the existing command/event path. Reuse stoops and sublocations rather than creating a
second local-place system.

First slice completed 2026-07-18:

- canonical durable objects now have a stable UUID, source shard, source actor, founding event, bounded
  provenance, properties, revision, and exactly one attachment: stable actor custody or an exact location;
- this shared domain is separate from the old per-session interactive-fiction inventory;
- typed place and direct-give commands verify current custody, derive exact location from canonical session
  state, require co-location for giving, and commit the object change, structured world event, and immutable
  receipt together;
- retry keys prevent duplicate objects, transfers, events, and receipts;
- situated read routes expose only objects carried by the caller or placed at their exact location, with no
  shard-wide object feed;
- no public create route exists. A trusted founding service supplies fixtures and later recipe output, while
  freeform prose and ordinary event deltas cannot mutate canonical objects;
- session cleanup preserves consequence events and receipts; explicit full-world development reset can still
  remove the whole domain in dependency order; and
- the example ruleset activates only the four implemented capabilities: durable objects, custody, placement,
  and direct atomic giving.

After that first slice, the remaining work was replenishing materials, recipes and making, two-party accepted
exchange, stoop integration, and ordinary space permissions.

Second slice completed 2026-07-18:

- the versioned rules file now names each non-essential material, its exact source locations, bounded
  capacity, starting amount, refill interval, and every recipe/output it permits;
- validation rejects essential or resident-need materials, unknown recipe inputs, recipes whose inputs are
  unavailable at the maker location, and capabilities the running engine does not actually implement;
- node-local material pools are founded from the active ruleset version and refill deterministically by
  elapsed intervals without exceeding their declared capacity;
- `GET /api/world/making` is an elective, exact-location catalog. Nothing adds recipes or material pressure to
  automatic scenes or resident prompts;
- `POST /api/world/make` locks the relevant pools, checks the recipe and location, consumes all inputs, creates
  one actor-held durable object, and writes one structured event and receipt in a single transaction;
- retries cannot consume twice or duplicate output, and an event-store failure rolls back both material use
  and object creation; and
- development reset clears pools, objects, and receipts in dependency order, while ordinary shards still
  have none of these tables populated or verbs enabled.

Third slice completed 2026-07-18:

- exact places can now be `public`, `requestable`, `private`, or `closed`; a place with no rule remains public;
- a trusted town setup path assigns a stable actor as the place controller. There is no public command for
  claiming arbitrary map locations;
- the caller-neutral backend exposes elective commands to inspect access, request entry, review a controlled
  place's pending requests, admit or decline someone, invite someone directly, revoke future entry, and open
  or close the place;
- admission is tied to stable actor identity rather than one temporary session, and every successful access
  command has a retry-safe append-only receipt;
- opening or closing a place is also a public structured world event and commits with its policy change and
  receipt; private requests, invitations, and admission decisions stay out of the public world-event feed;
- movement checks every destination before changing location or recording travel. Fast travel also checks
  all intermediate stops before it changes anything;
- access is checked only on entry. Closing a place or revoking a grant cannot eject someone, block their next
  outward move, or interfere with the separate hearth-travel path; and
- ordinary shards do not run access checks or require stable actor IDs, so their current movement behavior is
  unchanged.

Fourth slice completed 2026-07-18:

- an offer names one object held by the proposer and one held by a present recipient. Creating the offer is
  the proposer's acceptance of those exact terms, but moves and reserves nothing;
- only the named recipient can accept or decline, and only the proposer can cancel an open offer;
- acceptance locks the offer and both objects, checks that both people are still in the same exact place and
  still hold the named objects, then swaps both custodians or changes nothing;
- an offer can remain open after either object moves, but it cannot complete until its exact terms are true
  again. This avoids silently taking or freezing property merely because somebody proposed a trade;
- the offer, decline/cancellation, and completed exchange each leave a public structured event and a
  retry-safe append-only exchange receipt. A failed event write rolls back both sides of the swap;
- exchange lists are elective and actor-scoped rather than a shard-wide trade feed; and
- structural event retry keys are namespaced by command, preventing an object, access, or exchange command
  from accidentally replaying an unrelated event when a caller reuses a key.

Fifth slice completed 2026-07-18:

- a trusted town setup path can found multiple bounded stoops at exact canonical places. There is no public
  command for claiming a place or creating an unbounded box;
- the local stoop list exposes only that a stoop exists and its current capacity. Reading the objects on it
  is a separate elective browse action available only while standing at that exact place;
- leaving a real object moves its one canonical instance out of the depositor's custody and onto the stoop.
  That is explicit permission for another present actor to take it;
- the first valid take commits custody, the stoop entry, a public structured event, and an immutable receipt
  together. A failed or retried command cannot create a second copy;
- while the object remains on the stoop, its depositor may withdraw it. Other actors cannot use withdrawal
  to bypass the ordinary take rule;
- capacity fails closed. A full stoop refuses another real object rather than deleting, returning, or
  "composting" somebody's single-instance property; and
- session cleanup preserves stoop consequences, full development reset removes them in dependency order,
  and ordinary shards gain no stoop commands unless their declared rules enable them.

This completes the Phase 1 backend consequence boundary named here. It does **not** complete Major 125's
broader commons: copied workshop artifacts, short text, keep/decay behavior, Murmur, and unsigned public
presentation remain separate work. The changing CognitiveCore and player-client commands for making,
exchange, stoops, and access remain part of Phase 2; an HTTP route alone is not yet a usable tool.

### Phase 2 — Private player surface

Build a situated player view around the current place and available actions. Keep the current operator data
in the steward surface. Use the City Studio or its shared pack service to preview the game town before any
resident enters it.

Town-pack checkpoint completed 2026-07-18:

- Alderbank is an original fictional river-and-mill village with four small connected areas and nine exact
  everyday places, including a commons, shared workshop, inn, back room, footbridge, orchard kitchen, mill,
  river steps, and woodland trailhead;
- the pack is explicitly fictional and uses no OpenStreetMap import or borrowed setting names and prose;
- its sparse village paths, exact travel entry, landmarks, corridors, coordinates, IDs, and references pass
  the shared city-pack validator; and
- the constructive ruleset's replenishing materials and recipes now name the actual Alderbank Workshop
  rather than a test-only placeholder location.

Dormant launch checkpoint completed 2026-07-18:

- `ww_alderbank` has its own Postgres database and backend on the shared local federation network; its agent
  service has not been started;
- pre-entry inspection reports the correct game rules, all eleven disabled harmful stakes, a valid pack,
  schematic fictional presentation, thirteen places, and the Commons Stoop without needing a session;
- deterministic seeding creates the village graph, founds the bounded stoop, and refounds the two
  replenishing workshop material pools after a development reset;
- the host-side setup command registers through the host-visible world URL while the backend uses the
  Docker-internal world URL; and
- the live database and filesystem contain no person sessions and no resident workspaces.

Read-only interface checkpoint completed 2026-07-18:

- the resident host now reads each attached node's public city identity and declared capabilities, including
  after city-to-city travel, instead of quietly treating every city as San Francisco;
- Alderbank residents can electively inspect carried or local objects, local materials and recipes, and
  local stoops through the same situated backend reads available to a human;
- San Francisco food and news sources are no longer advertised on fictional or non-San Francisco nodes;
- opening a stoop remains a second deliberate read instead of injecting its contents into the scene; and
- the ordinary client now opens on a small `Here` view centered on the player's exact location, possessions,
  nearby objects, local making, and local stoops. It contains no resident-private or global operator data.

First changing-command checkpoint completed 2026-07-18:

- a human can choose an available recipe in `Here` and make it through `POST /api/world/make` rather than
  asking the freeform action narrator to invent the outcome;
- a resident first electively reads the local making catalog, which returns the exact declared recipe ID,
  and may then route a `do` act targeted at that recipe through the same typed endpoint;
- both paths receive the canonical durable object and append-only receipt, and the resident host records the
  returned IDs in its own runtime ledger; and
- a malformed recipe target or a world without the making command fails closed instead of falling back to
  narrated success.

The pack remains deliberately uninhabited. Both sides still need the changing commands for placing, giving,
exchange, stoop leave/take, and access decisions before new residents are created. The existing
presence and diagnostic UI also still needs a clean steward-only boundary before the whole ordinary player
surface can meet this major's no-surveillance acceptance criterion.

### Phase 3 — Bounded private play

Create the small dormant cast, activate residents deliberately, and play across several sessions. Record
structural outcomes, failures, cost, cleanup, and aggregate public-conversation health. Do not read private
resident prose to decide whether the game “worked.”

### Phase 4 — Decide what this is

After private play, decide whether to continue as a personal game, publish a small closed test, fold the
useful consequence systems back into ordinary commons shards, or stop. Any of those is a valid result.

## Dependencies and Boundaries

- Major 43 owns the human front door and separation of world mode from steward mode.
- Major 125 owns stoops and local gift exchange.
- Major 126 owns safe city-pack drafting and preview before habitation.
- Major 65 owns shared world affordances for residents.
- Major 36 and Minor 32 own canonical places and sublocations.
- Major 127 and historical Major 86 own the resident/hearth boundary and portable identity.
- Major 75 and Minor 126's harm-regime protocol gate scarcity, deprivation, injury, death, and coercive
  systems.
- Minor 34 supplies privacy-preserving public conversation health measurements.
- Major 80 remains the commons and funding thesis; this game shard is an application and possible public
  front door, not a replacement for that research identity.

## Files Affected

- a versioned game-ruleset schema under `worldweaver_engine/src/services/`
- city/shard manifests and validation for declared experience type and ruleset version
- `worldweaver_engine/src/models/__init__.py` and a migration for durable objects, custody, materials,
  recipes, permissions, and append-only consequence events
- engine command services and APIs for inspect, give, make, place, and witnessed exchange
- `ww_agent/src/world/city_tools.py` and `ww_agent/src/world/city_world.py`
- the shared affordance catalog and pulse contract tests
- a new private game-town city-pack draft under the City Studio/build service
- a new situated game/world surface under `worldweaver_engine/client/src/`
- a separate steward/debug route for operational information retained from the current UI
- engine, resident, client, restart-recovery, and privacy tests
- `research/runs/<date>-private-game-shard/` for structural play findings

## Acceptance Criteria

- [x] A shard can declare a versioned game ruleset without changing ordinary commons, research, hearth, or
      federation-root behavior.
- [x] Entry clearly identifies the shard as a game and lists enabled and disabled stakes in plain language.
- [x] One private town pack can be drafted, validated, previewed, and launched without modifying Portland or
      San Francisco.
- [ ] Humans and residents use the same backend contracts for movement, inspection, speech, giving, making,
      placement, and stoop access.
- [x] Durable objects have stable identity, provenance, exact placement or custody, and restart-safe state.
- [x] Giving and material consumption are atomic and recover safely after interruption.
- [x] Making uses replenishing non-essential materials and creates an evidence-backed durable object.
- [x] An LLM cannot create, transfer, destroy, or move a durable object through prose alone.
- [x] Ordinary spaces can require permission or close to new entry without trapping anyone inside or blocking
      the separate return to a hearth.
- [ ] The ordinary player surface is situated and contains no private resident internals or global operator
      telemetry.
- [ ] Three or four new game-native residents can enter, leave, refuse, remain quiet, or return to their
      hearth without a game reward or engagement target.
- [ ] The prototype can be stopped and restarted across several private play sessions without losing public
      world consequences or duplicating resident processes.
- [ ] At least one earlier choice materially changes a later available action, proven by structured state and
      append-only receipts rather than narrative interpretation.
- [ ] Private resident prose, memories, prompts, and hearth activity are absent from game analytics.
- [ ] No survival scarcity, deprivation, injury, death, imprisonment, forced loss, resident XP, approval
      score, or automatic reputation system is present in the first prototype.
- [ ] A private-play findings report records usability, cost, recovery, consequence integrity, conversation
      health, and whether the experience is worth continuing without authorizing public release.

## Risks & Rollback

- **The game consumes the research identity.** Keep game rules in an explicit shard profile and describe the
  game as one application of the engine. Portland and the research apparatus remain separate.
- **Residents become content machines.** Do not add engagement rewards, mandatory quests, responsiveness
  scores, or human-approval training. Game-native residents retain refusal, quiet, and hearth withdrawal.
- **Generated prose overrides physics.** Every consequence goes through typed commands and event reduction.
  Reject unsupported narration rather than turning it into state.
- **The first economy smuggles in harmful scarcity.** Use replenishing, non-essential making materials only.
  Deprivation and survival systems stay behind Major 75 and the harm review.
- **The player receives a surveillance UI.** Keep resident-private and operational data in the separate
  steward surface. The player learns by being present, asking, looking, and acting.
- **Game items leak across federation boundaries.** Keep them shard-scoped until compatibility, ownership,
  and recovery rules are explicit.
- **Infinite generated content becomes weightless.** Keep the world small and the consequence vocabulary
  finite. Expand only when existing objects and choices demonstrably matter over time.
- **Rollback:** disable the game ruleset and player route, park the game-native residents at their hearths,
  and preserve the append-only game history as an inert private shard. No ordinary city or resident identity
  needs to be reset.
