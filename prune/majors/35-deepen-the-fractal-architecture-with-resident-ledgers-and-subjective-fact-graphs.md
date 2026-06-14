# Deepen the fractal architecture with resident ledgers and subjective fact graphs

## Status

This major is active and now absorbs the remaining implementation intent of
Major 33.

The packet/intent/control-surface work mattered because it clarified resident
runtime boundaries, but the active implementation path is now ledger-first
resident architecture rather than further polishing transitional file
choreography.

## Problem

WorldWeaver's shard-first architecture is now strong at the world level, but the
fractal stops too early.

Today the architecture looks like this:

- federation root (`ww_world`) tracks shard registration, health, travelers, and
  federated residents
- city shards (`ww_sfo`, `ww_pdx`, etc.) maintain a canonical event log,
  projections, and semantic fact graph in Postgres
- residents still run on a different storage ontology: JSON files, markdown
  notes, ad hoc queues, and per-loop artifacts

That means the world and the resident do not share the same underlying pattern.
The shard knows how to answer:

- what happened?
- what is currently true?
- what facts are queryable?

The resident cannot answer those questions in the same way. Resident state is
spread across:

- `ww_agent/src/memory/working.py`
- `ww_agent/src/memory/provisional.py`
- `ww_agent/src/memory/retrieval.py`
- `ww_agent/src/memory/reveries.py`
- `ww_agent/src/memory/voice.py`
- `ww_agent/src/runtime/signals.py`
- `ww_agent/src/loops/slow.py`
- `ww_agent/src/resident.py`

This is still workable, but it becomes a liability as the project moves toward:

- memory consolidation
- developmental state
- learned preference weights
- inspectable adaptation
- cross-resident observability
- richer steward tooling

Those features want the same invariant the world already has: lived experience
should become structured state rather than only a pile of files.

The goal of this major is not to force every resident into a full database-first
rewrite immediately. The goal is to stop adding new bespoke resident storage
patterns and give the resident runtime the same ontology as the shard runtime:

- resident event ledger
- resident projections
- resident subjective fact graph

This is the "as above, so below" step that prepares the system for the
maturation-environment work in Major 34 without over-engineering it.

This major now absorbs the remaining useful intent of Major 33. The packet and
intent work was valuable because it clarified resident control boundaries, but
the next correct step is not to perfect bespoke file choreography. It is to make
packets, intents, grounding, movement, mail, and other resident runtime changes
first-class resident events that can drive ledger-derived projections.

## Proposed Solution

Introduce a resident-local storage and runtime contract that mirrors the shard
architecture while remaining incremental.

### Landed so far

This major is no longer only speculative. The first resident-fractal slices are
already in the codebase.

Landed implementation direction:

- `ww_agent/src/runtime/ledger.py` now provides an append-only resident runtime
  ledger, a reducer boundary, and rebuild helpers for derived artifacts
- `ww_agent/src/runtime/signals.py` now treats packet and intent lifecycle as
  ledger-backed state rather than only queue-file truth
- `ww_agent/src/loops/fast.py`, `ww_agent/src/loops/slow.py`,
  `ww_agent/src/loops/mail.py`, `ww_agent/src/loops/wander.py`, and
  `ww_agent/src/loops/ground.py` all emit resident runtime events for execution,
  route, mail, research, and movement behavior
- resident compatibility files such as `stimulus_packets.json`,
  `intent_queue.json`, `active_route.json`, and staged mail intent files are now
  increasingly treated as projections or exports rather than the canonical
  substrate
- the slow loop now reads reduced resident state for intent staging context
- resident reduced state is mirrored into shard session vars as a non-load-
  bearing shard-backed copy

The remaining work in this major is to deepen and normalize that substrate,
especially around reducer discipline, subjective fact updates, identity-growth
provenance, and eventual shard-backed canonical persistence.

### Phase 1 - Define the resident runtime ontology

Add explicit conceptual separation between:

- resident events
  - packets received
  - reflections produced
  - intents staged
  - actions executed
  - rest transitions
  - grounding observations
- resident projections
  - current concerns
  - active goals
  - relationship summaries
  - place affinity
  - current developmental state
- resident subjective facts
  - beliefs about self
  - beliefs about others
  - place-linked associations
  - preference weights
  - unresolved tensions

This phase is partly architectural and partly documentary. The key output is a
single resident-state contract that future work must target, even if some
projections remain file-backed at first.

### Phase 1A - Introduce a resident runtime ledger and first derived projections

Before deeper subjective-fact work, the resident runtime should stop treating
queue files as the only truth.

The first implementation slice should add:

- an append-only resident runtime ledger
- compatibility files that remain in place for loop continuity
- at least one derived projection computed from ledger history

Initial event classes should include:

- packets emitted / observed / ignored
- intents staged / claimed / executed / failed
- grounding observations
- research queue mutations and research results
- movement results
- mail decisions and sends

The projection layer can begin modestly:

- recent event timeline
- per-event-type counts
- last grounding / movement / mail / research observation

This is enough to start using ledger-first thinking without forcing a flag-day
rewrite of every resident memory file.

Status:

- landed in initial form
- resident runtime events, runtime projection, subjective projection,
  memory projection, and subjective facts now exist
- compatibility files still exist, but the canonical direction has shifted

### Phase 2 - Replace ad hoc files with ledger-derived projections

Refactor the resident runtime so the following become projections over a common
event substrate rather than isolated source-of-truth files:

- `working.json`
- `reveries.json`
- `voice.json`
- `stimulus_packets.json`
- `intent_queue.json`
- `soul_notes.md`

Identity evolution should also stop depending on raw note accumulation alone.
Major 42 will define the canonical soul / matured growth split, but this major
should provide the event and projection substrate that makes that split
inspectable and evidence-backed.

The immediate implementation does not have to delete every file. It should make
those files derived artifacts, snapshots, or caches rather than the only source
of truth.

This should align with the packet/intent work in Major 33:

- packets are resident events
- staged intents are resident events
- fast-loop execution receipts are resident events
- slow-loop reflection updates resident projections

At this point Major 33 should be considered structurally folded into this major.
Its remaining value is as precursor rationale, not as the primary active
implementation container.

Status:

- substantially underway
- packet queue, intent queue, route state, mail intent state, research queue
  state, and runtime snapshots are now derived from ledger history or rebuilt
  through the reducer path
- other resident memory surfaces are still mixed and need further unification
- soul-note evidence and identity-growth provenance are still too file-local and
  need to become ledger-backed

### Phase 3 - Introduce a resident subjective fact graph

Add a resident-scoped fact layer that uses the same pattern as the world fact
graph, but for inner life and subjective structure.

The resident graph should support facts such as:

- `self -> novelty_seeking -> 0.7`
- `self -> trusts -> sun_li`
- `self -> associates -> tea_house`
- `self -> avoids -> market_street`
- `self -> unresolved_about -> levi`
- `self -> has_matured_growth -> quiet_anchor`
- `self -> learned_from -> repeated_night_shift_exhaustion`

Required properties:

- confidence tier or weight
- temporal update history
- supersession / retirement logic
- queryability

This graph does not need to be identical to the shard graph. It does need to be
legible, inspectable, and migratable into the same family of tooling.

Status:

- started, but still immature
- `subjective_facts.json` now exists and is derived from runtime events
- current facts are still snapshot-like and heuristic
- the missing next step is a proper fact update model with supersession,
  evidence lineage, temporal retirement, and stronger query semantics
- this should explicitly support Major 42 so that "who the resident has become"
  is inspectable without rewriting canon blindly

### Phase 4 - Choose the storage boundary explicitly

Decide how resident event/projection/fact data is persisted.

The likely direction is shard-local Postgres, not one database per resident.
That means resident-level tables or scoped rows inside the shard database, with
resident identity as a first-class scope key.

Constraints:

- no requirement for a separate resident database process
- no requirement to fully remove file-backed exports
- support offline inspection and migration from current resident artifacts

This phase should keep the door open for filesystem snapshots, but make the
canonical storage contract compatible with queries rather than directory scans.

Status:

- not landed as canonical storage
- a shard-backed mirror exists through session vars, but this is intentionally
  non-load-bearing
- canonical resident truth is still file-backed ledger history

### Phase 5 - Unify tooling and observability across scales

Make the same kinds of operations possible at world, shard, and resident level:

- audit facts
- inspect recent events
- inspect active projections
- explain why a belief or preference exists
- trace "what experience led to this state change?"

This is the practical payoff of the deeper fractal. Steward tools, diagnostics,
and developmental inspection should not need a separate mental model at each
scale.

### Phase 6 - Extend the same ontology upward where useful

Once resident state is unified downward, revisit the federation root.

`ww_world` should remain operationally lightweight, but it may need its own
federation-level fact/projection layer for:

- cross-shard social continuity
- traveler identity history
- federation-wide presence summaries
- cross-shard narrative facts

This phase is explicitly lower priority than resident unification. It is included
so the architecture does not stop at the shard boundary in either direction.

### Design constraints

This major should avoid symmetry theater.

Do not:

- introduce a second bespoke resident storage system while calling it a ledger
- require every resident concern to become a full graph query on day one
- break current inspectability by hiding everything behind opaque abstractions
- tie every loop directly to SQL before the resident-state contract is stable

Do:

- stop inventing new one-off file formats for developmental state
- model new resident state so it could trivially become a row, event, edge, or projection
- prefer append-only history plus derived views
- keep migration incremental and reversible

## Files Affected

- `prune/majors/33-centralize-agent-inference-in-the-slow-loop-and-packetize-runtime-control.md`
- `prune/majors/34-reframe-worldweaver-as-a-maturation-environment-for-embodied-ai.md`
- `prune/WORLD_FACT_GRAPH.md`
- `prune/MULTI_TEMPO_AGENTS.md`
- `ww_agent/src/resident.py`
- `ww_agent/src/runtime/signals.py`
- `ww_agent/src/loops/slow.py`
- `ww_agent/src/loops/fast.py`
- `ww_agent/src/memory/*`
- `worldweaver_engine/src/models/*`
- `worldweaver_engine/src/services/*`
- shard-aware dev and audit tools that currently assume only world-level facts

## Acceptance Criteria

- [ ] A resident-state contract exists that explicitly separates resident events, projections, and subjective facts
- [ ] New resident runtime features stop introducing bespoke storage formats that cannot migrate into the ledger/projection/fact model
- [ ] Packet and intent history can be treated as resident events rather than only queue files
- [ ] At least one resident projection is derived from resident event history instead of maintained as an isolated source-of-truth file
- [ ] A resident-scoped subjective fact representation exists for self/other/place beliefs or preferences
- [ ] Steward/operator tooling can inspect resident state using the same basic query model used for shard/world state
- [ ] The design remains incremental: current resident files can be migrated or exported without requiring a flag-day rewrite

## Risks & Rollback

- The main risk is elegance for its own sake. If a resident-local fact graph is
  introduced before it carries real developmental or observability weight, the
  system gets more abstract without becoming more useful.
- A premature SQL-first rewrite could slow the loops down and make the runtime
  harder to inspect during the transition. Roll back by keeping file-backed
  exports and projections until the resident ledger contract is stable.
- If the resident ontology is too rigid, it may fight the packet/intent work
  rather than support it. Roll back by treating packets and intents as the first
  resident event classes instead of designing a separate parallel system.
- Federation-level graph work could sprawl and distract from the real leverage,
  which is resident-state unification. Roll back by treating federation extension
  as an optional later phase rather than part of the first implementation slice.
