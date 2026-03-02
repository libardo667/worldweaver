# Build a world memory graph and fact layer from world events

## Problem

`WorldEvent` records in `src/models/__init__.py` and `src/services/world_memory.py` are currently an append-only log. We can embed and search summaries, but we do not store durable entities, relationships, or fact states that can be queried as world knowledge. This makes "the world remembers" mostly implicit text, not explicit simulation state.

## Proposed Solution

1. Add graph-oriented persistence models for durable world knowledge:
   - `WorldNode` (entity/location/faction/object/concept)
   - `WorldEdge` (typed relation: allied_with, controls, damaged, rumors_about)
   - `WorldFact` or `WorldAssertion` (time-bounded truth claims linked to events)
2. Extend `record_event()` in `src/services/world_memory.py` to run a fact extraction pipeline:
   - deterministic extraction from `world_state_delta`
   - optional LLM extraction for narrative-only summaries
   - upsert nodes/edges/assertions with confidence metadata
3. Add graph query service methods for:
   - nearest facts by semantic query
   - neighborhood lookup from entity or location
   - current asserted facts at a location
4. Inject graph facts into runtime systems:
   - `src/services/command_interpreter.py` prompt context
   - `src/services/semantic_selector.py` context vector composition
5. Expose graph endpoints in `src/api/game.py` for debugging and frontend usage.

## Files Affected

- `src/models/__init__.py`
- `alembic/versions/*` (new migration)
- `src/services/world_memory.py`
- `src/services/command_interpreter.py`
- `src/services/semantic_selector.py`
- `src/api/game.py`
- `src/models/schemas.py`
- `tests/service/test_world_memory.py`
- `tests/api/test_world_endpoints.py`

## Acceptance Criteria

- [ ] A recorded event can create or update graph nodes/edges/assertions.
- [ ] Repeated events about the same entity merge into stable graph identities.
- [ ] Querying by entity/location returns current related world facts.
- [ ] Freeform action interpretation receives relevant world facts in prompt context.
- [ ] Semantic selection context includes graph-derived signals, not only raw event summaries.
- [ ] New graph endpoints return structured, typed data suitable for UI rendering.

## Risks & Rollback

Entity resolution errors can create duplicate nodes or bad links. Keep extraction confidence and source event IDs on every assertion, and allow disabling graph extraction with a feature flag. Roll back by turning off the flag and ignoring graph tables while retaining raw event logs.
