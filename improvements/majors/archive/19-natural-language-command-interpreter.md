# Add natural language command interpreter

## Problem

The vision describes hybrid interaction: "Storylets present choices, but
you can also type freeform actions. The AI interprets intent and resolves
against the world state." Currently the only interaction model is
selecting from a fixed list of choices. There is no way for a player to
type "I peek under the tarp when the merchant isn't looking" and have the
system respond.

## Proposed Solution

1. **Add `POST /api/action` endpoint** that accepts:
   ```json
   {
     "session_id": "...",
     "action": "I peek under the tarp when the merchant isn't looking"
   }
   ```

2. **Create `src/services/command_interpreter.py`** with:
   - `interpret_action(action: str, state_manager, world_memory, current_storylet) -> ActionResult`
   - Uses the LLM to:
     a. Parse the player's intent from natural language
     b. Check if the action is plausible given the current world state
     c. Determine the outcome (success/failure/partial)
     d. Generate a narrative response
     e. Compute state changes (variable updates, world events)
   - Returns an `ActionResult` with: narrative text, state deltas,
     whether a new storylet should fire, and optional choices for
     follow-up.

3. **The LLM prompt** includes:
   - Current storylet text and choices (context for what's happening)
   - Player's current state (inventory, location, relationships)
   - Recent world history (what's happened recently)
   - The player's starting goal
   - Instructions to stay consistent with established world facts

4. **After interpretation**, the system:
   - Applies state changes via the state manager
   - Records a WorldEvent (type: "freeform_action")
   - Optionally triggers a new storylet if the action moves the narrative

## Files Affected

- `src/services/command_interpreter.py` — new service
- `src/api/game.py` — new `/api/action` endpoint
- `src/models/schemas.py` — `ActionRequest` and `ActionResponse` schemas
- `tests/api/test_action_endpoint.py` — new tests

## Acceptance Criteria

- [ ] `POST /api/action` accepts freeform text and returns a narrative response
- [ ] The response includes state changes applied to the session
- [ ] Actions are recorded as WorldEvents
- [ ] Implausible actions get a graceful in-world rejection (not an error)
- [ ] The LLM response respects established world facts
- [ ] If LLM is unavailable, a fallback response acknowledges the action
- [ ] Tests cover: plausible action, implausible action, LLM fallback

## Risks & Rollback

LLM latency — freeform actions require a round-trip to the LLM, which
may take 2-5 seconds. Mitigation: streaming response, or a "thinking..."
indicator in the frontend. The LLM could also hallucinate state changes
that contradict world facts — mitigation: validate state deltas against
known constraints before applying. Rollback: remove the endpoint and service.
