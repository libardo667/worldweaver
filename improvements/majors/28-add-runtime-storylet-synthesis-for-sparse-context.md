# Add runtime storylet synthesis for sparse narrative context

## Problem

When eligible storylets are scarce or semantically weak for the current context, the experience can stall or feel repetitive. Current flow in `src/api/game.py` and `src/services/game_logic.py` relies on preexisting storylets and fallback text, which does not satisfy the "living world" goal.

## Proposed Solution

1. Add sparse-context detection in selection flow:
   - low eligible count
   - low top semantic score
   - high recent repetition
2. Introduce runtime storylet synthesis service:
   - generate 1-3 candidate storylets from current context, world facts, and active goal
   - enforce JSON schema for generated storylets
   - embed and score candidates before inclusion
3. Persist approved runtime storylets with provenance metadata:
   - `source = runtime_synthesis`
   - `seed_event_ids`
   - `expires_at` or relevance decay fields
4. Integrate synthesized storylets into normal selection and world-memory event recording.
5. Add guardrails for cost/latency with feature flags and rate limits.

## Files Affected

- `src/services/game_logic.py`
- `src/services/llm_service.py`
- `src/services/embedding_service.py`
- `src/services/semantic_selector.py`
- `src/api/game.py`
- `src/models/__init__.py`
- `alembic/versions/*` (optional migration for provenance fields)
- `tests/service/test_game_logic.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [ ] Sparse contexts trigger runtime synthesis under configured thresholds.
- [ ] Generated storylets pass schema validation before persistence/use.
- [ ] Synthesized storylets are semantically scored and selected through existing pipeline.
- [ ] Narrative stalls are reduced in seeded playthrough tests.
- [ ] Feature flags can disable synthesis without breaking `/api/next`.

## Risks & Rollback

Runtime generation can increase cost and latency and may introduce inconsistent quality. Use strict validation, low default limits, and kill switch flags. Roll back by disabling synthesis and returning to static storylet selection.
