# Build a non-canon projection BFS planner for world coherence

## Problem
Current turn generation was mostly single-step. The engine chose a storylet or action outcome for now, but did not keep a structured, low-cost projection tree of what was likely next. This caused trajectory drift, weaker long-horizon coherence, and slower adaptation when player intent changed.

## Proposed Solution
Implemented a world-planner lane that expands a bounded breadth-first projection tree with structured stubs, not prose.

1. Added a projection stub schema and session-scoped storage with explicit non-canon semantics (`non_canon=true`), depth, confidence, and TTL.
2. Added referee-lane scoring support for projected nodes (`allowed`, `confidence`, `projected_location`, `stakes_delta`, `risk_tags`, `seed_anchors`) with deterministic fallback when disabled or unavailable.
3. Added bounded frontier expansion (`max_depth`, `max_nodes`, `time_budget_ms`) with explicit budget exhaustion signaling.
4. Integrated expansion into prefetch/background weaving so projection generation is additive and does not block turn commit.
5. Added projection tree diagnostics metadata and turn-side projection seed metadata for observability.

## Files Affected
- `src/config.py`
- `src/models/schemas.py`
- `src/services/llm_service.py`
- `src/services/prefetch_service.py`
- `src/services/prompt_library.py`
- `src/services/state_manager.py`
- `src/services/turn_service.py`
- `tests/api/test_settings_readiness.py`
- `tests/service/test_projection_bfs.py`

## Acceptance Criteria
- [x] Projection stubs are generated as structured JSON with no required prose fields.
- [x] Projection storage clearly separates non-canon data from canonical world facts.
- [x] Bounded BFS expansion enforces max depth, max nodes, and max time budget.
- [x] Prefetch pipeline can populate projection stubs without mutating canonical session state.
- [x] Failing planner calls degrade safely without breaking `/api/next` and `/api/action`.

## Risks & Rollback
- Risk: projection expansion can increase token and latency costs if bounds are too loose.
- Risk: planner schema drift can create brittle parsing failures.
- Rollback:
  - Disable expansion quickly via `WW_ENABLE_V3_PROJECTION_EXPANSION=false` (or disable prefetch via `WW_ENABLE_FRONTIER_PREFETCH=false`).
  - Keep referee scoring disabled (default) or disable with `WW_ENABLE_PROJECTION_REFEREE_SCORING=false`.
  - Revert the major 101 implementation commits if needed; route contracts remain additive/stable.

## Validation Commands
- `pytest -q tests/service/test_projection_bfs.py tests/service/test_prefetch_service.py tests/api/test_prefetch_endpoints.py tests/api/test_settings_readiness.py tests/service/test_llm_service.py`
- `python scripts/dev.py quality-strict`

## Completion Note
- Status: done
- Archive target: `improvements/majors/archive/101-build-non-canon-projection-bfs-planner.md`
