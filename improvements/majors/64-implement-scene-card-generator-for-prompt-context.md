# Major 64: Implement Scene Card generator for prompt context

## Problem Statement
Currently, the LLM receives the full `_world_bible`, dozens of state variables, and accumulated facts on every turn. This sprawling JSON universe forces the model to act as a simulator, continuity editor, and narrator simultaneously. It leads to heavy semantic repetition (constantly repeating the same static anchors like "ozone" or "morning sun") and context bloating.

## Proposed Solution
Separate the "Referee/Planner" from the "Narrator" by implementing a Scene Card generator. The system will compile a small, canonical "Now" object each turn containing only the immediate context, and pass *that* to the LLM instead of the entire world state.

### Acceptance Criteria
- [ ] Create a `SceneCard` schema including:
  - `location` and `sublocation`
  - `cast_on_stage` (active NPC names present)
  - `immediate_stakes` (what is at risk right now)
  - `constraints` / `affordances` (e.g. "you can see: guard, gate, crate")
  - `active_goal` with `urgency` and `complication`
- [ ] Update `generate_world_confirmation` and `generate_action_consequences` to accept the `SceneCard` and a small fact pack instead of the full state dict.
- [ ] Verify that the LLM focuses on immediate scene geometry rather than repeating static World Bible themes.

## Expected Files Changed
- `src/models/schemas.py`
- `src/services/scene_service.py` (New or mixed into state/storylet selector)
- `src/services/llm_service.py`
- `src/api/game/story.py`
- `src/api/game/action.py`

## Rollback Plan
- Disable the Scene Card prompt injection flag (if added) or revert the LLM core prompt construction to pass the raw `state_manager` variables.
