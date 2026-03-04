# Add JIT beat generation prompt builder and `generate_next_beat()` LLM function

## Problem

The current per-turn flow (`src/api/game/story.py:api_next`) calls `pick_storylet_enhanced()` to select a pre-generated storylet, then calls `adapt_storylet_to_context()` to rewrite its text to reference recent events. This is **cosmetic** — the adaptation LLM call can style a scene to mention recent events, but it cannot change what the scene is fundamentally about.

The result is that the player's experience is a random walk through a bag of disconnected vignettes. Story events do not causally follow from each other.

This minor adds a new generation path: instead of selecting and adapting a pre-baked scene, the LLM writes **the next scene fresh** given what just happened. This is the JIT beat generator.

## Proposed Solution

### 1. New prompt builder in `prompt_library.py`

Add `build_beat_generation_prompt(world_bible, recent_events, current_vars, story_arc)` returning `(system_prompt, user_prompt)`.

**System prompt** includes:
- `NARRATIVE_VOICE_SPEC` (voice quality rules — always included)
- Focused rules about causal continuation (each beat must reference or follow from what came before)
- Output format instructions — compact, no exemplars needed

**User prompt** is a JSON context block containing:
```json
{
  "world_bible": { ...persisted bible from minor 73... },
  "recent_events": ["summary 1", "summary 2", "summary 3"],
  "current_state": { "location": "...", "key vars": "..." },
  "story_arc": { "act": "setup", "tension": "...", "turn_count": 4 },
  "instruction": "Write the next scene that causally follows from these events."
}
```

**Output schema** (compact beat format):
```json
{
  "title": "Scene title",
  "text": "Narrative prose (2–4 sentences, second person, present tense)",
  "choices": [
    {"label": "Choice label", "set": {"key": "value"}}
  ]
}
```

No `requires` field — JIT beats are generated contextually so they're always relevant.

### 2. New LLM function in `llm_service.py`

Add `generate_next_beat(world_bible, recent_events, current_vars, story_arc)` that:
- Calls `build_beat_generation_prompt()` to compose messages
- Calls `_chat_completion_with_retry()` with `max_tokens=400` (one scene is small)
- Parses the response with `_extract_json_object()`
- Validates: must have `text` (non-empty str) and `choices` (list of 2–3 items)
- Normalises choices through the existing `_normalize_adaptation_choices()` helper
- Returns the dict on success, raises `ValueError` on invalid output

Uses the existing retry/metrics infrastructure (`metric_operation="generate_next_beat"`).

### 3. Deterministic fallback

Add `_fallback_beat(current_vars)` — a deterministic function that returns a valid beat dict using no LLM, for use when AI is disabled or `generate_next_beat()` raises. The fallback uses the player's current `location` and `player_role` variables to compose minimal but valid prose.

## Files Affected

- `src/services/prompt_library.py` — add `build_beat_generation_prompt()`
- `src/services/llm_service.py` — add `generate_next_beat()` and `_fallback_beat()`

## Acceptance Criteria

- [ ] `build_beat_generation_prompt()` returns a `(str, str)` tuple
- [ ] The user prompt contains `world_bible`, `recent_events`, `current_state`, `story_arc` keys
- [ ] `generate_next_beat()` with AI disabled returns a valid fallback beat with `text` and `choices`
- [ ] `generate_next_beat()` with a mocked LLM response correctly parses and validates the beat
- [ ] A beat with missing `text` triggers fallback (no exception raised to caller)
- [ ] A beat with fewer than 2 choices triggers fallback
- [ ] `python -m pytest -q` passes
