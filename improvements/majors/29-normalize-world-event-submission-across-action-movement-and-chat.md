# Normalize world-event submission across action, movement, and chat

> **MERGE NOTE (2026-06-08):** this is the **engine-side half of Major 66 (log edges, not
> nodes)** — same problem (an inconsistent, untrustworthy world-event ledger), engine side
> rather than cognitive side. Do this as part of #66, not as a competing path. Major 69 also
> depends on this: the turn-pipeline can only be removed once event submission is unified here.

## Problem

The engine currently has multiple incompatible paths for creating "world events,"
which makes the world ledger uneven and hard to trust.

Concrete problems visible in the current system:

- Freeform actions go through the full turn pipeline in
  `worldweaver_engine/src/services/turn_service.py`: intent extraction, reducer
  commit, narration, canonical `record_event`, and fact-graph updates.
- Map movement in `worldweaver_engine/src/api/game/world.py` writes `WorldEvent`
  rows directly, bypassing `record_event`, projection handling, and graph
  extraction entirely.
- Local and city chat in `worldweaver_engine/src/api/game/world.py` do call
  `record_event`, but only as a best-effort utterance event with
  `skip_graph_extraction=True`, so the fact graph does not receive any durable
  assertion that speech happened at all.
- This means some surfaces contribute structured state to the fact graph and some
  do not, even though all of them are player-visible world activity.
- As a result, the world fact graph is not yet a credible unified ledger of what
  has happened in the world over time.

This is an engine-contract problem. Before agents become more sophisticated about
how they interact with the world, the world interface itself needs to define what
counts as a canonical event and what durable fact each event surface contributes.

## Proposed Solution

Normalize non-storylet world activity so freeform actions, movement, and chat all
submit through the same canonical event recorder, with explicit decisions about:

- whether the event is part of history
- whether it contributes structured facts to the graph
- whether it should update the projection table

The immediate goal is not to narrate every surface the same way. It is to make the
ledger coherent and inspectable.

### Phase 1 - Canonical event-submission contract

- Treat `worldweaver_engine/src/services/world_memory.py::record_event` as the
  single canonical entry point for world-event persistence.
- Remove direct `WorldEvent(...)` insertion from API routes.
- Extend `record_event` so callers can explicitly control:
  - graph extraction
  - projection writes
  - structured fact payloads for low-noise surfaces

### Phase 2 - Normalize movement events

- Route map-based movement in `worldweaver_engine/src/api/game/world.py` through
  `record_event` instead of direct DB writes.
- Give movement events a structured world-fact payload so the graph records facts
  like:
  - actor location
  - whether movement is still in transit
- Keep movement history legible with origin/destination semantics, but avoid
  forcing event-history-shaped payloads into projection until movement projection
  semantics are fully defined.

### Phase 3 - Normalize chat events without graph-noise explosion

- Keep chat transcripts in `LocationChat` as the real-time surface.
- Continue recording utterance events in world history, but replace the current
  "skip graph extraction entirely" behavior with low-noise structured facts such as:
  - a speaker was observed speaking at a location
- Do not dump raw message text into graph facts by default.
- This preserves world memory and presence traces without turning the graph into
  an unbounded transcript store.

### Phase 4 - Define projection policy per surface

- Explicitly distinguish:
  - canonical state-change events that should update projection
  - historical/ephemeral events that should remain in history + fact graph only
- Freeform actions can continue updating projection through the turn pipeline.
- Movement and chat should only update projection once their delta semantics are
  canonical rather than event-history-shaped.

### Phase 5 - Diagnostics and operator visibility

- Make it easy to inspect for one route:
  - event row written
  - graph facts written
  - projection rows written or intentionally skipped
- Add tests that prove movement and chat now contribute to the ledger in a stable,
  intentional way.

## Files Affected

- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/src/services/world_memory.py`
- `worldweaver_engine/src/services/turn_service.py`
- `worldweaver_engine/tests/api/test_world_endpoints.py`
- `improvements/majors/23-rest-cycles-and-agent-dormancy.md`
- `improvements/majors/28-stage-agent-intents-before-execution.md`

## Acceptance Criteria

- [ ] Movement no longer writes `WorldEvent` rows directly from the route handler
- [ ] Movement contributes structured world facts through the canonical event recorder
- [ ] Chat continues to write transcript history and now contributes at least one low-noise structured fact to the graph
- [ ] Raw chat text is not blindly promoted into world facts by default
- [ ] Projection writes are explicitly controlled per surface instead of being an accidental side effect
- [ ] Tests cover movement and chat ledger behavior end to end
- [ ] The engine has one clearer definition of what it means for a surface to "submit a world event"

## Risks & Rollback

- If raw utterances are pushed into the graph without a narrow schema, the fact
  graph will become transcript sludge. Keep utterance facts low-noise and
  structured.
- If movement events are forced into projection without separating origin/history
  from canonical state, projection can become misleading. Keep projection opt-in
  per surface.
- If route handlers keep bespoke event writes after this pass, the interface will
  remain conceptually muddy even if tests pass. Normalize the write path first.
- Rollback path: keep `record_event` additive, migrate movement and chat one at a
  time, and preserve route response payloads so user-facing behavior stays stable
  while the ledger contract is cleaned up.
