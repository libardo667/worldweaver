# Enforce reducer-only canon commit and projection invalidation rules

## Problem
Speculative projections are useful for speed and coherence, but they become dangerous if treated as facts. Without strict commit boundaries, stale or conflicting projections can leak into canonical state and create hard-to-debug narrative contradictions.

## Proposed Solution
Define and enforce canonical commit boundaries at the reducer layer.

1. Projections remain non-canon until a player-triggered turn is validated and committed by reducer logic.
2. Commit operations reference projection IDs for traceability, but only committed effects mutate canonical state.
3. After commit, invalidate projection branches that conflict with updated state or fall outside TTL/budget.
4. Add request-boundary rollback safety so failed writes cannot poison subsequent turns.
5. Record clear diagnostics (`selected_projection_id`, `commit_status`, `invalidated_projection_count`) in logs/artifacts.

## Files Affected
- `src/services/rules/reducer.py`
- `src/services/turn_service.py`
- `src/services/state_manager.py`
- `src/services/prefetch_service.py`
- `src/api/game/story.py`
- `src/api/game/action.py`
- `tests/service/test_reducer.py`
- `tests/service/test_state_manager.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria
- [ ] No projection-only field can mutate canonical state without reducer commit.
- [ ] Projection branch invalidation runs after each successful commit.
- [ ] Failed commit paths always rollback transactional state.
- [ ] Turn diagnostics include selected projection and invalidation telemetry.
- [ ] Integration tests confirm non-canon data cannot leak into canonical world history.

## Risks & Rollback
- Risk: aggressive invalidation can reduce prefetch hit rates.
- Risk: commit/invalidation coupling can introduce race conditions under concurrent load.
- Rollback: disable projection binding at commit, keep reducer behavior as current baseline, and retain projection data as read-only diagnostics.
