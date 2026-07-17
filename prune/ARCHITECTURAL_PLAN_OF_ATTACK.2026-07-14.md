# Architectural plan of attack — 2026-07-14

This is the working architectural sequence for WorldWeaver after reviewing the live majors and minors
under `prune/` against the code they name. It is a durable coordination document, not a replacement for
the individual work items: each implementation still belongs in its major or minor and must satisfy that
item's acceptance criteria and evidence requirements.

**Execution update (2026-07-17):** the full relevance/completion sweep is recorded in
`WORK_ITEM_AUDIT.2026-07-14.md`. Root CI, document currency, the engine event-spine consolidation, and
Major 85's resident-ledger durability work, Major 66's relational event schema, Major 35's narrow
resident-state contract, Major 63's physical speech transport, Major 64's plural world-salience
projection, and Major 84's substrate-native rest contract are complete. Major 15's projection audit
resolved to keep the reducer-produced materialized view; Stable work items now have one canonical home
here. The immediate implementation target is Major 86's shared resident/hearth capability boundary.

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
- WorldWeaver owns the resident host and capability ecology; Stable is read-only source lineage;
- keeper/FileScope/MCP capabilities remain optional grants and must not become universal city-resident facts.

## Executive sequence

1. Restore trustworthy CI and current architectural guidance.
2. Unify engine event submission and finish deleting the turn pipeline. **Complete.**
3. Fix the resident ledger's append and reduction cost model. **Complete.**
4. Complete relational events and narrow the resident-state ontology around evidence-backed claims.
   **Complete.**
5. Complete physical speech topology and plural world salience, then build the shared resident/hearth
   capability seam. **Speech and salience complete.**
6. Build identity, private hearth attachment, federation travel, correspondence, observatory, and
   human-facing surfaces outward from those stable contracts.

## Architectural baseline

The live architectural baseline is now:

- The engine submits action, movement, speech, bootstrap, and system events through one canonical
  application service. `/api/action` is a lean action service rather than a narrative-turn orchestrator.
- The resident runtime has already moved to the substrate + predictive pulse under
  `ww_agent/src/runtime/`; `CognitiveCore`, the resident ledger, reducers, perception, and effectors are the
  live architecture.
- Current guidance describes the CognitiveCore architecture; superseded loop-era guidance is historical.

There are also two related but distinct event-sourced systems:

- The engine/world ledger is Postgres-backed through
  `worldweaver_engine/src/services/world_memory.py`.
- The resident ledger is file-backed through `ww_agent/src/runtime/ledger.py`.

They share an event-sourcing philosophy, but do not yet have clean enough mutation, schema, projection,
or persistence contracts to carry the later architecture safely.

## Milestone A — make the repository trustworthy

### A1. Root CI — complete (archived Minor 61)

The only GitHub Actions workflow still lives under `worldweaver_engine/.github/workflows/`, so it is not a
repository-root workflow. Minor 61 is also stale where it names `narrative-eval-smoke`, which Major 69
deleted with the storylet/next pipeline.

The corrected root gates should cover:

- engine tests and lint;
- agent tests and lint;
- client typecheck and build;
- the public leak sweep;
- a check against references to deleted narrative-evaluation machinery where useful.

### A2. Document currency — complete (archived Major 81)

This should be a factual rewrite, not a prose expansion:

- replace `ww_agent/AGENTS.md` with current guidance;
- rewrite `ww_agent/src/README.md` around the live runtime;
- remove current-doc references to deleted `src/loops/` and `src/memory/` packages;
- re-baseline roadmap claims against actual work-item status;
- update Minor 38's proposed frontend decomposition, since several suggested hooks already exist and the
  guild surfaces it names have been retired.

### A3. Repair and retire Major 76's substrate-sync invariant — complete

Commit `507557d` repaired the former source classifications. The subsequent ownership decision retired
the sync tool entirely: WorldWeaver is canonical, so no external manifest can overwrite its substrate.

### Exit condition

Repository-root CI exercises the engine, agent, and client, and a new contributor or agent is directed to
the architecture that actually runs.

## Milestone B — give the engine one event spine — complete

### B1. Define canonical world-event submission — complete

World-event writes formerly split among:

- `worldweaver_engine/src/services/turn_service.py`;
- movement and speech routes in `worldweaver_engine/src/api/game/world.py`;
- `record_event()` in `worldweaver_engine/src/services/world_memory.py`.

The application-level event-submission contract now owns:

- command/event validation;
- reducer invocation;
- persistence;
- projection update and invalidation;
- a consistent response/receipt boundary.

Action, movement, public chat, bootstrap, and system events now route through it. `/api/action` follows the
lean path Major 69 names: **interpret → validate → reduce → record**.

Private mail is deliberately not a `WorldEvent`: `/api/world/history` exposes that table, while DMs are
private by contract. Keep delivery in `DirectMessage` until the Major 66/72 relational envelope can carry
directed edges with explicit visibility. Unification must not make private correspondence public.

### B2. Finish Major 69 slice 3 — complete

After no event write depended on the turn orchestrator, the implementation:

- deleted `turn_service.py`;
- moved the retained pure action helpers from `src/services/turn/` to `src/services/action/`, then deleted
  the turn package;
- deleted `orchestration_adapters.py` and turn-only compatibility types;
- replaced orchestration-mechanism tests with action/event-contract and reducer-authority tests.

Do not retain a generic turn abstraction merely because an action arrives as an HTTP request. The target
world is command/event-driven, not narrative-turn-driven.

### B3. Honor archived Major 15's WorldProjection decision

The audit resolved Outcome C: `WorldProjection` is a reducer-produced materialized view of canonical
events and is load-bearing in action, movement, speech, rebuild, and overlay tests. Preserve that model
while tightening event ownership:

- keep projection writes behind canonical event reduction;
- prohibit new direct mutation authorities;
- keep reset/rebuild operations explicit and tested.

Do not mechanically apply the resident slogan "the ledger is the only state" to the engine. Durable
materialized projections are compatible with event sourcing; competing mutation authorities are not.

The event-path work preserved this already-proven ownership while removing the turn orchestrator.

### Exit condition

The reducer is the only canonical world-state mutation authority, every production command retains its
event-ledger write, and no live code describes a storylet/turn runtime.

## Milestone C — make the resident substrate durable

### C1. Execute Major 85 through the canonical substrate owner — complete

The resident ledger now appends without rewriting history, keeps the complete cold log, uses a guarded
hot window for short-lived calculations, and advances an atomic versioned checkpoint during normal work.
Complex projections rebuild from at most the newest 10,000 events; only checkpoint recovery rereads the
complete file. Golden and performance tests cover output agreement, recovery, retention beyond the old
limit, and flat normal-update cost as cold history grows. The completed work item is archived at
`prune/history/majors/85-unbounded-ledger-the-append-only-log-should-actually-be-append-only.md`.

### C2. Complete Major 66's architectural event schema — complete

Phase 1 is effectively complete and its addressee-based `in_reply_to` decision is locked. Do not reopen
it. Complete the schema needed for deterministic relational queries:

- stable actor identity and location on relevant perceptions and acts; **complete (2026-07-17)**
- `co_present` on the event at which presence is known; **complete (2026-07-17)**
- recipient-side perception events at prompt ingestion time; **complete (2026-07-17)**
- `resident_seeded` with stable provenance from `runtime/doula.py`; **complete (2026-07-17)**
- stable identifiers across speech transport, perception, and reply edges; **complete (2026-07-17)**
- a versioned edge schema rather than accumulating ungoverned payload keys. **complete (2026-07-17)**

The completed Phase 2 uses a versioned envelope and immutable `utterance_perceived` events. A resident
does not count as having perceived a line merely because polling returned it: the event is written when
that line enters a prompt. The edge can be derived by joining the sender's canonical `utterance_id` and
the recipient's `utterance_perceived`; mutating the original utterance would violate the append-only
model.

The completed Phase 3 writes a resident's birth facts to that resident's ledger before boot and one shared
`cohort_config` entry per doula process to its administrative ledger. This makes the actual configuration
inspectable without treating it as resident thought or scheduling a live cohort run. Major 66 is archived
at `prune/history/majors/66-log-edges-not-just-nodes-the-relational-ledger.md`.

### C3. Re-baseline Major 35 into a smaller resident-state contract — complete

Major 35 has the right destination but names deleted implementation surfaces and treats already-landed
phases as future work. Narrow the remaining contract to four layers:

1. immutable resident events;
2. reducer checkpoints;
3. derived projections;
4. provenanced subjective claims and edges.

The ticket is now re-baselined. Prove the model with one relationship-knowledge vertical slice:

```text
utterance perceived
→ reply edge
→ relationship projection
→ subjective claim with evidence IDs
→ inspectable steward view
```

This gives supersession, evidence lineage, temporal state, and query semantics a real use case before the
project invents a general subjective fact graph.

The relationship slice is complete and archived at
`prune/history/majors/35-deepen-the-fractal-architecture-with-resident-ledgers-and-subjective-fact-graphs.md`.
It proves event → projection → evidence-backed claim → mirror inspection without inventing a general fact
graph. Belief provenance stays with Major 56.

Keep canonical resident truth file-backed during this milestone. First make the contract correct,
versioned, reproducible, and inspectable; decide on shard Postgres only after that.

### C4. Reconcile identity and growth governance

Archived Major 42 plus active Majors 56/58 and archived Major 61 describe overlapping architectural
generations. Do not reintroduce Major 42's
deleted `slow.py`/soul-note mechanism. Preserve its constitutional concern in the newer model:

- canonical identity is immutable;
- growth is a separate append-only, evidence-backed layer;
- promotion follows archived Major 61's provenance rules;
- beliefs follow Major 56's provenance model;
- matured growth follows Major 58's concordance gate;
- rendered `SOUL.md` is a projection/export, never the in-place source of truth.

### Exit condition

Complete resident history is retained, per-event runtime cost is bounded, relational facts are recorded at
the edge-forming moment, and a resident claim can be traced to immutable evidence.

## Milestone D — make the world structurally plural

### D1. Execute Major 63 (physical speech topology) — complete

The live transport now treats monoculture first as a routing problem, not a personality problem:

- local speech is the default;
- addressing an absent person uses a private carry rather than a citywide fallback;
- only an explicit city target broadcasts;
- immutable events distinguish local, citywide, carried, heard, overheard, and directly addressed
  speech, with stable relationship evidence;
- the pulse contract tells residents what those target choices mean.

Minor 32 does not need to be folded into this completed routing slice. It remains optional map texture and
has been reassigned to Major 36, where child-location and occupancy semantics actually belong.

### D2. Complete Major 64 (plural salience) — complete

Plural salience is now a resident-side projection over independent world sources, not another prompt
filter. It can retain:

- local world events;
- physical speech;
- environmental changes;
- ambient presence;
- personal relationships;
- traversal encounters.

The reducer preserves the latest competing feature clusters and exposes source count, dominant share, and
effective feature count. Ambient descriptions remain outside the default prompt and are available through
the elective `surroundings` source. This makes a one-note scene measurable without forcing a second
authored topic into it. Major 62 remains deferred because its own analysis correctly identifies
composition as the weakest lever.

Reconsider Minor 33 here as cheap local environmental texture, not as a population of simulated full
residents.

### D3. Execute Major 84 (substrate-native rest) — complete

Rest is derived from circadian wakefulness plus sustained low arousal, published through the runtime
mirror, and consumed by the live rest-metrics endpoint and client. Deep-night calm now returns without a
model call, while ignition/direct address still wakes the resident. The old tuning-based schedule summary
is gone.

Keep Minor 62's dark-room classifier out of the immediate implementation queue until the ledger records
enough input novelty and diversity provenance to distinguish starvation from legitimate habituation.

### D4. Begin Major 86 at the capability boundary

Before adding Major 65's seed kit to `city_tools.py`, extract one typed elective-source/capability contract
usable by both HearthWorld and CityWorld. Correct FileScope provenance so authorized reading is not rendered
as already-held local knowledge. Classify faculties such as mirror, lots, provenance-on-self, and measure as
resident-scoped; classify city walks, letters, traces, and local world sources as world-scoped. **The shared
source boundary and the first shared resident host are complete as of 2026-07-17.** The host now ports
Stable's proven live swap, but requires confirmed city retirement and rebuilds world-scoped sources before
activating the keeper-free hearth.

The current hearth is a durable actor-home attachment on the resident host; it does not require one engine
process or database per resident. City-to-city transfer remains separate. Before that expansion, Major 37
must inspect `worldweaver_engine/scripts/build_city_pack.py` so adding cities, shard discovery, and travel
destinations share one city identity contract.

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
- archived Minor 57's boundary measurement application;
- Minor 63's live threshold calibration;
- further doula/casting runs under Major 32.

Also defer:

- Major 78 research synthesis;
- Major 80 thesis/publication work;
- Minor 37 until Major 43 settles the interface;
- any live Stable-era research imported as Majors 114–121 or Minors 120–129 unless separately promoted.

## Immediate next work item

The next implementation ticket should be:

> **Major 86 — finish shared-host convergence without duplicating the resident**

Majors 69, 85, 66, 35, 63, 64, and 84 have settled the event path, durable log, relationship evidence,
small resident-state projection, physical speech routing, inspectable plural world inputs, and derived
rest. Major 86's source boundary and live same-daemon hearth switch are now implemented using the resident's
existing durable `actor_id`. The remaining Major 86 work is to reconcile useful hearth capabilities from
Stable and retire the duplicate standalone familiar boot path without universalizing keeper-only grants.

Do not generalize this same-daemon hearth switch into city-to-city transfer yet. That later Major 37 work
needs the full federation identity, shard handoff, and destination model; start its discovery by reading
`worldweaver_engine/scripts/build_city_pack.py` and treating multi-city creation as part of the travel
contract rather than a separate hard-coded deployment concern.

## Maintenance rule for this document

Update this plan only when an architectural dependency, ownership decision, or milestone exit condition
changes. Record implementation detail and evidence in the owning major/minor instead. When the sequence is
no longer current, archive this file under `prune/history/` rather than silently rewriting it into a record
of a different plan.
