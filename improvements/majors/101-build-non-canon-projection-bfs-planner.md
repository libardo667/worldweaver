# Build a non-canon projection BFS planner for world coherence

## Problem
Current turn generation is mostly single-step. The engine chooses a storylet or action outcome for now, but it does not keep a structured, low-cost projection tree of what is likely next. This causes trajectory drift, weaker long-horizon coherence, and slower adaptation when player intent changes.

## Proposed Solution
Implement a world-planner lane that expands a bounded breadth-first projection tree with structured stubs, not prose.

1. Add a projection stub schema and session-scoped storage with explicit non-canon semantics (`non_canon=true`), depth, confidence, and TTL.
2. Use the referee lane as the world planner to score candidate next moves and emit structured projection stubs (`allowed`, `confidence`, `projected_location`, `stakes_delta`, `risk_tags`, `seed_anchors`).
3. Expand only a bounded frontier (top-K candidates, depth <= 2 by default) under strict node and time budgets.
4. Integrate this into prefetch/background weaving so projection generation is additive and never blocks turn commit.
5. Persist projection artifacts for observability and replay diagnostics.

## Files Affected
- `src/models/schemas.py`
- `src/services/prefetch_service.py`
- `src/services/llm_service.py`
- `src/services/prompt_library.py`
- `src/services/state_manager.py`
- `src/services/turn_service.py`
- `tests/service/test_llm_service.py`
- `tests/service/test_turn_service.py`
- `tests/api/test_prefetch_endpoints.py`

## Acceptance Criteria
- [ ] Projection stubs are generated as structured JSON with no required prose fields.
- [ ] Projection storage clearly separates non-canon data from canonical world facts.
- [ ] Bounded BFS expansion enforces max depth, max nodes, and max time budget.
- [ ] Prefetch pipeline can populate projection stubs without mutating canonical session state.
- [ ] Failing planner calls degrade safely without breaking `/api/next` and `/api/action`.

## Risks & Rollback
- Risk: projection expansion can increase token and latency costs if bounds are too loose.
- Risk: planner schema drift can create brittle parsing failures.
- Rollback: disable projection expansion with feature flags and fall back to current scene-card-only turn generation while preserving route contracts.
