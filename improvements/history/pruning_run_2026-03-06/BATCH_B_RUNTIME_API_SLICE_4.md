# Batch B Runtime API Slice 4

Date: `2026-03-06`
Status: `completed`

## Scope
- Consolidate duplicated route-start wrapper setup in game API endpoints.
- Keep endpoint behavior/contracts unchanged.

## Changes
1. Extended shared runtime helper:
- `src/api/game/runtime_helpers.py`
  - added `RouteRuntimeContext`
  - added `begin_route_runtime(...)`

2. Rewired endpoint setup to helper:
- `src/api/game/story.py`
- `src/api/game/action.py` (`/api/action` path)
- `src/api/game/turn.py`

3. Preserved stream-specific behavior:
- `src/api/game/action.py` (`/api/action/stream`) still binds metrics context inside stream generator as before.

## Guardrail Verification
Commands:
- `ruff check src/api/game/runtime_helpers.py src/api/game/story.py src/api/game/action.py src/api/game/turn.py src/api/game/orchestration_adapters.py`
- `pytest -q tests/api/test_story_endpoint.py tests/api/test_action_endpoint.py tests/api/test_turn_endpoint.py tests/api/test_game_endpoints.py`
- `python scripts/dev.py quality-strict`

Results:
- Lint: pass
- Targeted endpoint tests: `84 passed`
- Full strict gate: pass (`578 passed`; warning budget unchanged)

Note:
- One transient failure appeared once in strict run (`test_next_applies_pending_choice_commit_storylet_effects_once`) and reproduced as pass on immediate rerun; final strict run passed. This aligns with prior flaky behavior noted during pruning.

## Duplication Map Impact
Addressed additional request-wrapper duplication not explicitly split in the original map:
- route setup boilerplate (`trace_id`, metrics route bind, response trace header, request-start timestamp, timing dict seed).

Remaining notable runtime_api simplification candidate:
- action stream event-phase helper consolidation (optional; lower leverage than completed slices).
