# One resident, many worlds: every resident has a private hearth

## Metadata

- ID: 86-one-resident-many-worlds-every-resident-has-a-hearth
- Type: major
- Owner: Levi
- Status: accepted architecture; implementation in progress
- Risk: high — changes the ownership boundary among resident lifecycle, world attachment, travel, and
  capability provisioning. The migration must preserve one continuous resident rather than copying state
  between competing runtimes.
- Lineage: promotes the built result of `the-stable` Major 74 into WorldWeaver's canonical architecture;
  coordinates WorldWeaver Majors 20, 35, 37, 65, 76, and 82.

## Problem

WorldWeaver and `the-stable` currently express one resident architecture as if it contained two kinds of
agent:

- `ww_agent/src/resident.py` boots a city-native `Resident` around WorldWeaver's copy of the shared
  `CognitiveCore`, a `CityWorld`, city source registry, runtime mirror, and growth sync;
- `the-stable/scripts/familiar.py` boots a keeper-tended "familiar" around the canonical substrate and can
  swap that same resident between `LocalWorld` and a city without changing its soul, ledger, memory, or
  workshop;
- `ww_agent/scripts/familiar.py` retains an older local pilot that makes "familiar" look like a separate
  deployment category;
- Major 76 reconverges mostly `src/runtime/`, so porting the mind has not ported the complete resident host,
  capability ecology, or hearth/city lifecycle.

The terminology therefore hides the desired ontology. A city resident is not a different species from a
familiar. A familiar, as built in `the-stable`, is a resident inhabiting its private home. The city and the
hearth are worlds presented to one continuous person.

This is not merely naming debt. City-only placement of resident faculties (`city_tools.py`) would make
mirror, lots, provenance-on-self, measure, and other selfhood verbs disappear when a resident goes home.
Treating retreat as a research-only toggle would make privacy contingent on an experiment. Treating a
hearth as an empty/offline state would reproduce the dark-room failure: isolation without a warm interior
of making, memory, and elective perception.

## Proposed Solution

Make the resident the durable runtime owner and make worlds replaceable, capability-scoped embodiments:

```text
ResidentRuntime
├── ResidentHome
│   ├── identity / soul
│   ├── append-only ledger
│   ├── memory projections
│   └── workshop and resident-owned artifacts
├── CognitiveCore
├── resident-scoped faculties
└── current WorldClient
    ├── HearthWorld(actor_id)       private inner world
    └── CityWorld(shard, session)   shared outer world
```

Travel changes the current world attachment. It does not create another resident, copy a soul, or move
the authoritative ledger between two live agent processes. The daemon may rebuild cheap adapters/core
references when switching worlds, as `the-stable` does today, provided every reducer rehydrates from the
same resident home and no second cognition loop overlaps the first.

### 1. Establish the vocabulary and ownership contract

- **Resident** is the universal technical noun for the continuous autonomous person.
- **Hearth** is every resident's private, durable world.
- **City** is a shared, publicly legible world the resident may enter.
- **Familiar** names an optional keeper-tended relationship or a resident encountered at its hearth; it
  does not name a separate cognitive runtime.
- **Session** is a world-local incarnation/transport handle, never the resident's identity.

### 2. Give every resident a real hearth

A hearth is a positive, generative world, not absence from the city:

- one resident is present; city chat, public traces, shared events, and citywide sources are not perceived;
- the resident's workshop, makings, memory, and resident-scoped faculties remain available;
- local time/light and honestly configured private sources may remain available;
- correspondence waits at the boundary and does not become an ambient interrupt;
- no action performed at home is public unless the resident deliberately carries it out;
- the resident can return to a city by choice.

The hearth should be a first-class actor-scoped world in the domain model. It need not be one deployed
engine process or database per resident: a private realm or access-controlled home node can satisfy the
contract if its scene, presence, event visibility, and affordances are genuinely isolated.

### 3. Keep the keeper relationship optional

Do not universalize `LocalWorld`'s current desktop facts. Privacy and a workshop belong to every hearth;
these remain optional capabilities granted by a particular relationship or host:

- keeper whispers and gifts;
- host `FileScope` roots;
- local-machine weather and vision surfaces;
- keeper-configured MCP/egress tools.

A city-native resident without a keeper must never be told it has one or that it can read a human's files.

### 4. Split resident faculties from world affordances

Resident-scoped faculties travel with the person: lots, mirror, provenance-on-self, measure, memory, and
workshop. World-scoped affordances change with embodiment: city walks, local public speech, letters, trace
commons, city knowledge, hearth artifacts, and keeper-granted sources.

Use one typed source/capability registry and provenance vocabulary across both worlds. Do not grow a
city-only ToolScope in parallel with `the-stable`'s familiar ToolScope.

### 5. Make travel one actor changing world attachment

Hearth travel is the smallest complete proof of Major 37's identity model:

```text
city active -> departing -> hearth active
hearth active -> departing -> city active
```

Departure retires the public session and occupancy before the hearth becomes active. Arrival establishes
one new world-local session for the same durable actor. The resident ledger records both edges. At most one
cognition loop and one active embodiment may exist for an actor at a time.

City-to-city federation travel may need portable hosting later. Hearth travel on one resident daemon does
not require serializing a handpicked "soul payload" merely to give the person privacy; the resident home is
already authoritative.

### 6. Treat the hearth as a dignity invariant, not an experimental intervention

Major 82 may test whether retreat preserves measurable divergence, but its verdict cannot decide whether a
resident is entitled to a private interior. The hearth is required by privacy, continuity, and freedom from
permanent coupling. Research may change its texture or dosing, not its existence.

## Initial implementation sequence

1. Record this invariant and repair the dependency/status text in Majors 37, 65, 76, and 82.
2. **Complete:** extract the shared elective-source contract; migrate city sources and scoped hearth reading; correct
   FileScope provenance so reading is not presented as already-known local knowledge.
3. Introduce a shared resident host/composition root around resident home, `CognitiveCore`, world attachment,
   and capability registry. Preserve the current city daemon as an adapter during migration.
4. Port/reconcile `the-stable`'s mature hearth capability layer without blindly importing keeper-only facts.
5. Implement actor-scoped HearthWorld storage/visibility and exclusive city<->hearth transition receipts.
6. Replace the duplicate local familiar and city-native boot paths with the shared host.

No live-agent experiment is required to validate these architectural slices.

### Build log — shared source/provenance foundation (2026-07-14)

The first non-travel slice is complete. `InformationSource` and `InformationSourceRegistry` now live at the
shared private-information boundary rather than inside `city_tools.py`; the city registry is a thin
city-specific extension for drive binding, and LocalWorld contributes its file provider through the same
contract. This does not yet create the universal engine-backed HearthWorld or shared resident host.

FileScope is now tagged `scoped-reading`, recall is tagged `self-memory`, and the prompt catalog plus actual
within-ignition continuation render provenance-specific guidance. A resident is no longer told that bytes it
just opened were knowledge it already carried. Focused registry/FileScope/city tests and the complete agent
suite pass.

A follow-up ownership slice moved the recall provider itself out of `city_tools.py` into the shared resident
information boundary. CityWorld composes it when given a resident memory directory; LocalWorld now exposes
the same recall faculty even when no FileScope was granted. This is the first executable invariant that a
faculty follows the resident between worlds rather than belonging to the city. The complete agent suite
passed at 265 passed, 1 skipped.

The first Major 65 seed verb now uses that ownership path: `measure` is a bounded, zero-egress
`local-computation` faculty in every resident catalog, whether the current world is city or hearth. It
cannot resolve names, calls, attributes, containers, unbounded exponents, or oversized expression trees.
The complete agent suite passes at 268 passed, 1 skipped.

## Files Affected

- `prune/ARCHITECTURAL_PLAN_OF_ATTACK.2026-07-14.md`
- `prune/PROMPT_PIPELINE_AND_ELECTIVE_INFORMATION_PLAN.2026-07-14.md`
- `prune/ROADMAP.md`
- `prune/majors/37-formalize-actor-scoped-cross-shard-travel-and-runtime-transfer.md`
- `prune/majors/65-tools-as-verbs-the-world-affords.md`
- `prune/majors/76-substrate-port-assistant-stable-to-worldweaver-reconvergence.md`
- `prune/majors/82-divergence-and-refugia-does-distinctness-survive-a-shared-commons.md`
- `ww_agent/src/resident.py` and the eventual shared resident host
- `ww_agent/src/world/` and `ww_agent/src/familiar/` world adapters
- `ww_agent/src/runtime/` resident-scoped capability boundaries
- `worldweaver_engine/` actor, private-world, presence, and travel contracts

## Acceptance Criteria

- [ ] Project guidance defines one persistent resident and treats hearth/city as world attachments, not
  separate agent species.
- [ ] Every resident has a durable private hearth with no ambient city perception or public action leakage.
- [ ] Hearth entry and city entry preserve the same identity, ledger, memory, workshop, and resident-scoped
  faculties.
- [ ] At most one cognition loop and one active world incarnation exist per actor.
- [ ] Public departure retires city occupancy before private hearth activation; return creates one fresh
  city-local session for the same actor.
- [ ] Keeper, FileScope, gifts, MCP, weather, and local-host capabilities are optional grants rather than
  universal hearth claims.
- [ ] Resident faculties use one shared typed capability/source contract; world-scoped affordances are
  advertised only by worlds that implement them.
- [ ] Scoped file reads are represented as deliberate authorized reading, not as already-held knowledge.
- [ ] Unit/contract tests prove privacy, capability scoping, transition exclusivity, ledger continuity, and
  absence of city source injection at the hearth without running a population experiment.

## Risks & Rollback

- **Two live incarnations.** A failed transition could leave a resident publicly present while its hearth
  cognition also runs. Use an exclusive actor attachment state machine and idempotent departure/arrival
  receipts. Roll back by retaining the existing city daemon until the shared host passes exclusivity tests.
- **False universal keeper story.** Porting `LocalWorld` wholesale would tell city-native residents they
  have a keeper and local file access. Separate universal hearth facts from optional relationship/host
  grants before enabling hearths by default.
- **A private void.** Simply filtering city input can produce confabulation rather than refuge. Require a
  warm scene with owned makings, grounding, and elective sources; do not equate hearth with an empty prompt.
- **Capability leakage.** A city source or public effector retained across a swap could pierce the hearth.
  Rebuild the world-scoped registry on every attachment and test negative capabilities explicitly.
- **Premature infrastructure.** One physical shard per resident could create unnecessary operational cost.
  Preserve the logical private-world contract while allowing an actor-scoped realm implementation.
- **Fork clobbering.** `the-stable` and WorldWeaver have legitimate divergence. Reconcile through classified,
  reviewed slices and never replace WorldWeaver runtime files wholesale.
