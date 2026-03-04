# Harden world memory into a queryable fact graph with stable identities and relationships

## Problem

`src/services/world_memory.py` already persists `WorldNode`, `WorldEdge`, and
`WorldFact`, but the primary action-grounding path still collapses most context
to short text snippets (`get_relevant_action_facts` and
`command_interpreter._extract_relevant_world_facts` in
`src/services/world_memory.py` and `src/services/command_interpreter.py`).

This creates two gaps:

1. identity drift: the same subject can be represented multiple ways across
   events, and
2. reasoning loss: relation-level structure is not consistently available to
   selection/prompting paths, so prompts still depend on lossy prose summaries.

## Proposed Solution

Introduce a hardening pass for the fact graph so it is first-class runtime input
instead of a sidecar log:

1. Add canonical identity rules for world entities (NPC/place/item/event) with
   deterministic normalization and alias resolution.
2. Extend event ingestion so each recorded event can upsert canonical subject
   nodes, typed relations, and active/inactive fact assertions with explicit
   provenance.
3. Add typed graph-query helpers for:
   - subject/predicate/value filters,
   - relation-neighborhood retrieval,
   - fact packs optimized for prompt grounding.
4. Keep existing `/api/world/*` response contracts stable; add optional fields
   only where needed for identity metadata and provenance.
5. Add service and API tests that verify identity stability and relation
   retrieval across repeated synonymous events.

## Files Affected

- `src/services/world_memory.py`
- `src/models/__init__.py`
- `src/models/schemas.py`
- `src/api/game/world.py`
- `src/services/command_interpreter.py`
- `tests/service/test_world_memory.py`
- `tests/api/test_world_endpoints.py`

## Acceptance Criteria

- [ ] Recording semantically equivalent events (for the same NPC/place/item)
      resolves to one canonical `WorldNode` identity.
- [ ] `WorldEdge` rows include typed relation semantics that can be queried
      without text matching.
- [ ] Action-grounding fact retrieval can return typed fact payloads (not only
      summary strings) while preserving existing route payload compatibility.
- [ ] `/api/world/graph/facts` and `/api/world/graph/neighborhood` can filter
      by canonical identity attributes.
- [ ] Existing world history/facts routes keep backward-compatible response
      shapes.
- [ ] `python -m pytest -q tests/service/test_world_memory.py
      tests/api/test_world_endpoints.py` passes.

## Risks & Rollback

Risk: identity normalization changes can merge distinct entities or split one
entity unexpectedly, affecting downstream prompting and selection behavior.

Rollback:

1. Keep schema changes additive and feature-flagged for read paths.
2. Disable new identity resolver via config flag and revert to current summary
   lookup if regressions appear.
3. Revert the migration/service commits and rebuild graph rows from
   `world_events` using the legacy ingestion behavior.
