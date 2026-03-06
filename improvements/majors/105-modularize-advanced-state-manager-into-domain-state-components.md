# Modularize AdvancedStateManager into domain state components

## Problem
`AdvancedStateManager` currently concentrates inventory, relationships, environment state, goals/arcs, narrative beats, and change history in one surface. This makes boundary ownership unclear, raises regression risk for unrelated changes, and makes domain-focused testing harder as complexity grows.

## Proposed Solution
Split state responsibilities into domain-specific components behind one stable session controller.

1. Introduce a lightweight session-level orchestrator that keeps the current public `AdvancedStateManager` contract stable for API/reducer callers.
2. Extract owned domain components (for example: inventory, relationships, environment, goals/arcs, beats/history) with explicit mutation methods and invariants.
3. Move serialization/deserialization responsibilities into domain-aware adapters so persistence remains deterministic.
4. Add compatibility shims for legacy access patterns with explicit removal criteria.
5. Expand tests to verify behavioral parity before and after modularization.

## Files Affected
- `src/services/state_manager.py`
- `src/services/session_service.py`
- `src/services/rules/reducer.py`
- `src/models/schemas.py`
- `tests/service/test_state_manager.py`
- `tests/service/test_reducer.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria
- [ ] Existing reducer and route call sites keep backward-compatible behavior.
- [ ] Domain state responsibilities are extracted into bounded, testable components.
- [ ] Persistence round-trips preserve inventory/relationship/environment/goal/beat state without loss.
- [ ] Compatibility shim paths are documented with explicit retirement conditions.
- [ ] Regression tests prove parity for existing gameplay flows.

## Validation Commands
- `pytest -q tests/service/test_state_manager.py tests/service/test_reducer.py`
- `pytest -q tests/api/test_game_endpoints.py tests/api/test_action_endpoint.py`
- `python scripts/dev.py quality-strict`

## Risks & Rollback
- Risk: contract drift during extraction can break reducer-driven state writes.
- Risk: serialization boundaries may introduce subtle data-shape regressions.
- Rollback: keep legacy `AdvancedStateManager` path behind a feature flag and revert to monolithic behavior until parity gaps are closed.
