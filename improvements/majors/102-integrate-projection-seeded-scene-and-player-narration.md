# Integrate projection-seeded scene narration and player hint rendering

## Problem
The narrator currently receives scene-card context but often starts from an under-specified future model. This can produce coherent local prose while still missing trajectory continuity. Player-facing signals also lack explicit clarity levels that indicate confidence and speculative depth.

## Proposed Solution
Feed selected projection stubs into scene narration and add a limited-knowledge player hint channel.

1. On each turn, map the chosen action or choice to one projection stub from the non-canon tree.
2. Pass `scene_card_now + selected_projection_stub + goal_lens` into narrator generation.
3. Add a lightweight player-hint response channel that exposes limited perspective hints without leaking full projection internals.
4. Attach clarity metadata (`unknown`, `rumor`, `lead`, `prepared`, `committed`) to response diagnostics and map nodes.
5. Keep narrator output bounded and grounded: one selected stub plus at most one alternate contrast stub.

## Files Affected
- `src/services/turn_service.py`
- `src/services/llm_service.py`
- `src/services/prompt_library.py`
- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/models/schemas.py`
- `tests/api/test_game_endpoints.py`
- `tests/api/test_action_endpoint.py`
- `tests/service/test_prompt_and_model.py`

## Acceptance Criteria
- [ ] Scene narration receives a selected projection stub in adaptation context.
- [ ] Player hint payloads are generated from limited context and do not leak full projection trees.
- [ ] Clarity levels are emitted consistently for relevant turn outputs.
- [ ] Route contracts remain backward compatible (additive fields only, no required removals/renames).
- [ ] Regression tests cover projection-seeded narration and hint payload behavior.

## Risks & Rollback
- Risk: additional context fields may increase prompt complexity and latency.
- Risk: hint channel can accidentally expose non-canon details.
- Rollback: disable projection-seeded prompts and hint channel via flags, returning to prior scene-card narration path.
