# Add player goal and narrative arc tracking

## Problem

The vision expects players to start with a simple goal that gets complicated by emergent events. Current APIs and state composition do not model goals explicitly, so selection and adaptation cannot intentionally redirect or escalate a player arc.

## Proposed Solution

1. Add explicit goal state to session data:
   - primary goal text
   - optional subgoals
   - urgency and complication signals
   - milestone history
2. Add endpoints to set/update goals and mark milestones.
3. Include goal embedding in semantic context for storylet scoring.
4. Update command interpretation so freeform actions can progress, derail, or branch goals.
5. Add arc timeline in state summary for debugging and UI rendering.

## Files Affected

- `src/models/schemas.py`
- `src/services/state_manager.py`
- `src/services/semantic_selector.py`
- `src/services/command_interpreter.py`
- `src/api/game.py`
- `tests/service/test_state_manager.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [x] Session state stores and returns a structured primary goal.
- [x] Storylet scoring shifts when goal context changes.
- [x] Freeform actions can update goal progress and complications.
- [x] Arc timeline is visible in state summary/debug output.
- [x] Tests verify goal persistence across session reloads.

## Risks & Rollback

Poorly tuned goal weighting can over-constrain emergent play. Keep weighting configurable and expose debug scoring to tune gradually. Roll back by excluding goal signals from semantic scoring while keeping stored goal data.
