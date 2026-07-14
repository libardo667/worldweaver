# Architectural plan of attack — 2026-07-14

This is the working architectural sequence for WorldWeaver after reviewing the live majors and minors
under `prune/` against the code they name. It is a durable coordination document, not a replacement for
the individual work items: each implementation still belongs in its major or minor and must satisfy that
item's acceptance criteria and evidence requirements.

The immediate direction is **consolidation of the event and ledger architecture**, not more live-agent
experiments, model tuning, casting runs, or behavioral calibration on machinery whose contracts are still
moving.

## Architectural correction — one resident, many worlds

Major 86 records a dependency that this plan previously omitted: `the-stable`'s hearth resident and
WorldWeaver's city resident are not two agent species. The resident is the continuous owner of identity,
ledger, memory, workshop, and cognition; hearth and city are world attachments. Every resident must have a
private hearth it can enter without being exposed to the city current, and travel must change embodiment
without creating or copying a second mind.

This is an architectural requirement, not a live-agent experiment and not a verdict deferred to Major 82.
It changes the placement of later work:

- resident faculties and the elective-source contract must be shared before Major 65 grows more city-only
  tools;
- Major 37 must model hearth entry as one actor swapping world attachment, with exclusive presence;
- Major 76 must ultimately reconcile the resident host and capability ecology, not only runtime files;
- keeper/FileScope/MCP capabilities remain optional grants and must not become universal city-resident facts.

## Executive sequence

1. Restore trustworthy CI and current architectural guidance.
2. Unify engine event submission and finish deleting the turn pipeline.
3. Fix the resident ledger's append and reduction cost model.
4. Complete relational events and narrow the resident-state ontology around evidence-backed claims.
5. Build physical speech topology, plural world salience, and the shared resident/hearth capability seam.
6. Build identity, private hearth attachment, federation travel, correspondence, observatory, and
   human-facing surfaces outward from those stable contracts.

## Architectural baseline

Three generations of architecture remain visible at once:

- The engine still retains a large per-turn orchestration system in
  `worldweaver_engine/src/services/turn_service.py`; it remains load-bearing because it owns world-event
  writes for `/api/action`.
- The resident runtime has already moved to the substrate + predictive pulse under
  `ww_agent/src/runtime/`; `CognitiveCore`, the resident ledger, reducers, perception, and effectors are the
  live architecture.
- Guidance still describes deleted loop-era packages. `ww_agent/AGENTS.md` is explicitly marked
  superseded but remains an instruction surface, and several README/module maps still name deleted
  `src/loops/` and `src/memory/` machinery.

There are also two related but distinct event-sourced systems:

- The engine/world ledger is Postgres-backed through
  `worldweaver_engine/src/services/world_memory.py`.
- The resident ledger is file-backed through `ww_agent/src/runtime/ledger.py`.

They share an event-sourcing philosophy, but do not yet have clean enough mutation, schema, projection,
or persistence contracts to carry the later architecture safely.

## Milestone A — make the repository trustworthy

### A1. Re-baseline and execute Minor 61 (root CI)

The only GitHub Actions workflow still lives under `worldweaver_engine/.github/workflows/`, so it is not a
repository-root workflow. Minor 61 is also stale where it names `narrative-eval-smoke`, which Major 69
deleted with the storylet/next pipeline.

The corrected root gates should cover:

- engine tests and lint;
- agent tests and lint;
- client typecheck and build;
- the public leak sweep;
- a check against references to deleted narrative-evaluation machinery where useful.

### A2. Execute Major 81 (document currency)

This should be a factual rewrite, not a prose expansion:

- replace `ww_agent/AGENTS.md` with current guidance;
- rewrite `ww_agent/src/README.md` around the live runtime;
- remove current-doc references to deleted `src/loops/` and `src/memory/` packages;
- re-baseline roadmap claims against actual work-item status;
- update Minor 38's proposed frontend decomposition, since several suggested hooks already exist and the
  guild surfaces it names have been retired.

### A3. Repair Major 76's substrate-sync invariant

Fix the unmanifested `source_gate.py` failure recorded during Major 83 before changing canonical substrate
files. A broken sync test is an unacceptable foundation for the ledger change in Milestone C.

### Exit condition

Repository-root CI exercises the engine, agent, and client, and a new contributor or agent is directed to
the architecture that actually runs.

## Milestone B — give the engine one event spine

### B1. Define canonical world-event submission

Today world-event writes are split among:

- `worldweaver_engine/src/services/turn_service.py`;
- movement and speech routes in `worldweaver_engine/src/api/game/world.py`;
- `record_event()` in `worldweaver_engine/src/services/world_memory.py`.

Create one application-level event-submission contract that owns:

- command/event validation;
- reducer invocation;
- persistence;
- projection update and invalidation;
- a consistent response/receipt boundary.

Route action, movement, public chat, and system events through it. Reduce `/api/action` to the lean path
Major 69 names: **interpret → validate → reduce → record**.

Private mail is deliberately not a `WorldEvent`: `/api/world/history` exposes that table, while DMs are
private by contract. Keep delivery in `DirectMessage` until the Major 66/72 relational envelope can carry
directed edges with explicit visibility. Unification must not make private correspondence public.

### B2. Finish Major 69 slice 3

Once no event write depends on the turn orchestrator:

- delete `turn_service.py`;
- delete `src/services/turn/`;
- delete `orchestration_adapters.py` and turn-only compatibility types;
- replace orchestration-mechanism tests with event-contract and reducer-authority tests.

Do not retain a generic turn abstraction merely because an action arrives as an HTTP request. The target
world is command/event-driven, not narrative-turn-driven.

### B3. Decide Major 15's WorldProjection contract

Major 15's wake-up trigger fires as part of this milestone. Decide it in terms of ownership:

- If `WorldProjection` is a reducer-produced materialized view of canonical events, keep it, document it,
  and prohibit direct mutation.
- If it overlays session state outside the canonical reducer, delete it and move legitimate shared state
  into explicit reducer-owned projections.

Do not mechanically apply the resident slogan "the ledger is the only state" to the engine. Durable
materialized projections are compatible with event sourcing; competing mutation authorities are not.

The likely result is **keep the projection, tighten its contract**, but the event-path work must prove it.

### Exit condition

The reducer is the only canonical world-state mutation authority, every production command retains its
event-ledger write, and no live code describes a storylet/turn runtime.

## Milestone C — make the resident substrate durable

### C1. Execute Major 85 through the canonical substrate owner

The current append path in `ww_agent/src/runtime/ledger.py` loads the whole file, appends one event,
rewrites and truncates the file, re-runs every reducer, and rewrites projections. That is O(n²) over a run
and silently destroys history after 10,000 events.

Implement:

- true O(1) JSONL append;
- bounded hot reads for short-timescale reducers;
- incremental/checkpointed state for genuinely long-timescale reducers;
- atomic checkpoint/projection writes;
- explicit checkpoint and projection format versions;
- golden tests proving existing arousal, grief, mood, anchor, and growth outputs do not change;
- a performance test showing flat append/reduction cost as cold history grows;
- an explicit guard relating runtime read windows to reducer timescales.

Land this in the canonical substrate owner and reconverge through Major 76. Do not create a
WorldWeaver-local fork of `ledger.py`.

### C2. Complete Major 66's architectural event schema

Phase 1 is effectively complete and its addressee-based `in_reply_to` decision is locked. Do not reopen
it. Complete the schema needed for deterministic relational queries:

- stable actor identity and location on relevant perceptions and acts;
- `co_present` on the event at which presence is known;
- recipient-side perception events at ingestion time;
- `resident_seeded` with stable provenance from `runtime/doula.py`;
- stable identifiers across speech transport, perception, and reply edges;
- a versioned edge schema rather than accumulating ungoverned payload keys.

Prefer immutable recipient-side perception events over retroactively adding `perceived_by` to an earlier
utterance. The edge can be derived by joining `utterance_sent` and `utterance_perceived`; mutating the
original utterance would violate the append-only model.

### C3. Re-baseline Major 35 into a smaller resident-state contract

Major 35 has the right destination but names deleted implementation surfaces and treats already-landed
phases as future work. Narrow the remaining contract to four layers:

1. immutable resident events;
2. reducer checkpoints;
3. derived projections;
4. provenanced subjective claims and edges.

Prove the model with one relationship-knowledge vertical slice:

```text
utterance perceived
→ reply edge
→ relationship projection
→ subjective claim with evidence IDs
→ inspectable steward view
```

This gives supersession, evidence lineage, temporal retirement, and query semantics a real use case before
the project invents a general subjective fact graph.

Keep canonical resident truth file-backed during this milestone. First make the contract correct,
versioned, reproducible, and inspectable; decide on shard Postgres only after that.

### C4. Reconcile identity and growth governance

Majors 42, 56, 58, and 61 describe overlapping architectural generations. Do not implement Major 42's
deleted `slow.py`/soul-note mechanism. Preserve its constitutional concern in the newer model:

- canonical identity is immutable;
- growth is a separate append-only, evidence-backed layer;
- promotion follows Major 61's provenance rules;
- beliefs follow Major 56's provenance model;
- matured growth follows Major 58's concordance gate;
- rendered `SOUL.md` is a projection/export, never the in-place source of truth.

### Exit condition

Complete resident history is retained, per-event runtime cost is bounded, relational facts are recorded at
the edge-forming moment, and a resident claim can be traced to immutable evidence.

## Milestone D — make the world structurally plural

### D1. Execute Major 63 (physical speech topology)

Treat monoculture first as a transport/topology problem, not a personality problem:

- local speech by default;
- deliberate addressed carry across locations;
- physical/path-aware propagation;
- immutable speech-transport events;
- explicit distinctions among heard, overheard, carried, and directly addressed speech.

Fold in or retire Minor 32 here. Ephemeral sublocations are useful only if they become a clean child-location
layer under the same actor/location/event contracts.

### D2. Complete Major 64 (plural salience)

Plural salience should be a world projection over independent sources, not another prompt filter. Candidate
sources include:

- local world events;
- physical speech;
- environmental changes;
- ambient presence;
- personal relationships;
- traversal encounters.

The reducer should preserve multiple competing salient clusters and expose dilution/competition
explicitly. Do not build Major 62 first; its own analysis correctly identifies composition as the weakest
lever.

Reconsider Minor 33 here as cheap local environmental texture, not as a population of simulated full
residents.

### D3. Execute Major 84 (substrate-native rest)

Derive rest from circadian wakefulness plus sustained low arousal, publish it through the runtime mirror,
and make the live rest-metrics endpoint consume the projection. This distinguishes resting residents from
stalled residents without reintroducing an external scheduler.

Keep Minor 62's dark-room classifier out of the immediate implementation queue until the ledger records
enough input novelty and diversity provenance to distinguish starvation from legitimate habituation.

### D4. Begin Major 86 at the capability boundary

Before adding Major 65's seed kit to `city_tools.py`, extract one typed elective-source/capability contract
usable by both HearthWorld and CityWorld. Correct FileScope provenance so authorized reading is not rendered
as already-held local knowledge. Classify faculties such as mirror, lots, provenance-on-self, and measure as
resident-scoped; classify city walks, letters, traces, and local world sources as world-scoped.

This slice does not yet require engine-side hearth storage or a live resident transition. It prevents the
next constructive features from deepening the false city/familiar fork.

### Exit condition

Locality and plurality are properties of world transport and state, and operational quiet is legibly
derived from the substrate rather than imposed or guessed.

## Milestone E — build outward from stable identity and event contracts

Sequence the later city/product architecture as follows:

1. **Major 20** — one canonical federation-wide `actor_id`.
2. **Major 86** — every actor has a private hearth; one resident host swaps exclusive world attachment.
3. **Major 37** — actor-scoped cross-shard travel and portable continuity, using hearth travel as the first
   complete transition contract.
4. **Major 36** — viewport map, graph navigation, and truthful occupancy.
5. **Majors 39 and 72** — durable public and private correspondence channels.
6. **Major 71** — steward observability surface.
7. **Major 18** — public observatory deployment.
8. **Major 43 + re-baselined Minor 38** — rebuild the front door and client shell around settled product
   modes.

Major 70 (AI-spend observability) is relatively orthogonal and may be pulled earlier if operating cost is
blocking development. It should use the same append-only event/accounting pattern.

Major 25 remains parked. Collapsing `worldweaver_engine` and `ww_agent` would create broad path churn
without fixing their real boundary; their HTTP separation is currently cleaner than their internal
architectures.

### Exit condition

Human, resident, travel, correspondence, occupancy, and observatory surfaces consume the same stable
actor and event contracts.

## Explicitly excluded from the current architectural queue

The following work depends primarily on running, measuring, tuning, or training agents and is excluded
until the machinery above is trustworthy:

- Major 51's per-mind model training;
- Major 60's pending live validation;
- Major 62's casting experiments;
- Major 73's pen-strength/marination study;
- Majors 74, 75, and 77, plus Major 82's population experiment;
- Minor 57's boundary measurement;
- Minor 63's live threshold calibration;
- further doula/casting runs under Major 32.

Also defer:

- Major 78 research synthesis;
- Major 80 thesis/publication work;
- Minor 37 until Major 43 settles the interface;
- Minor 64's cross-repo work-item cleanup until Major 85 exercises the substrate ownership boundary with
  real evidence.

## Immediate next work item

The next implementation ticket should be:

> **Canonical world-event submission and turn-pipeline demolition**

It should be executed as Major 69 slice 3, coordinated with the event-submission intent previously carried
by Major 29 and the event/edge contract in Major 66. It also wakes Major 15 at exactly the right moment.

This is the highest-leverage next change because it:

- removes the largest surviving block of obsolete architecture;
- gives every engine command one mutation and persistence contract;
- protects the world ledger during demolition;
- clarifies the projection boundary;
- makes later identity, topology, and observability work substantially cheaper to reason about.

Major 86's shared capability/provenance extraction may proceed as a bounded parallel architectural slice:
it does not depend on running residents, alter the engine event spine, or implement travel ahead of actor
identity. Do not proceed from that extraction into city<->hearth runtime switching until Major 20/37's
identity and exclusivity contracts are ready.

## Maintenance rule for this document

Update this plan only when an architectural dependency, ownership decision, or milestone exit condition
changes. Record implementation detail and evidence in the owning major/minor instead. When the sequence is
no longer current, archive this file under `prune/history/` rather than silently rewriting it into a record
of a different plan.
