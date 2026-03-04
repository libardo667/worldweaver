# Add world bible prompt builder and `generate_world_bible()` LLM function

## Problem

World creation currently calls `generate_world_storylets()` (`src/services/llm_service.py:982`) to produce 15 storylets in a single LLM batch (~4000 output tokens), which takes 30–60+ seconds and produces content that has no narrative causality between scenes.

The root fix is to replace this with a **world bible** — a compact (~200–300 token) structured document that captures locations, NPCs, central tension, and entry point. This is generated once at onboarding, persisted in session state, and reused on every subsequent JIT beat prompt instead of being regenerated.

This minor adds the **generation layer** without yet wiring it into the onboarding flow (that's minor 75).

## Proposed Solution

### 1. New prompt builder in `prompt_library.py`

Add `build_world_bible_prompt(description, theme, player_role, tone)` that returns `(system_prompt, user_prompt)`. The output schema is a compact JSON object:

```json
{
  "locations": [
    {"name": "...", "description": "one line"}
  ],
  "npcs": [
    {"name": "...", "role": "...", "motivation": "..."}
  ],
  "central_tension": "The one question or conflict that drives everything.",
  "entry_point": "Where and how the player arrives. One sentence.",
  "world_name": "A proper name for this place."
}
```

The system prompt uses `NARRATIVE_VOICE_SPEC` but **does not** include `QUALITY_EXEMPLARS` or `STORYLET_FORMAT_SPEC` — those are storylet-specific and not needed here.

### 2. New LLM function in `llm_service.py`

Add `generate_world_bible(description, theme, player_role, tone)` that:
- Calls `build_world_bible_prompt()` to compose messages
- Calls `_chat_completion_with_retry()` with `max_tokens=600` (bible is small)
- Parses the response with `_extract_json_object()`
- Validates: must have `locations` (non-empty list), `central_tension` (str), `entry_point` (str)
- Returns the dict on success, raises `ValueError` on invalid output

The function uses the existing retry/metrics infrastructure (`_log_llm_call_metrics`, `metric_operation="generate_world_bible"`).

### 3. Fallback

If `generate_world_bible()` raises, callers should catch and fall back to the existing `generate_world_storylets()` path. The fallback logic lives in minor 75 (wiring); this minor only adds the generation function.

## Files Affected

- `src/services/prompt_library.py` — add `build_world_bible_prompt()`
- `src/services/llm_service.py` — add `generate_world_bible()`

## Acceptance Criteria

- [ ] `build_world_bible_prompt()` returns a `(str, str)` tuple with non-empty system and user prompts
- [ ] The user prompt includes the world description, theme, player_role, and tone
- [ ] `generate_world_bible()` with AI disabled (`DW_DISABLE_AI=true`) returns a valid fallback bible dict with all required keys
- [ ] `generate_world_bible()` with a mocked LLM response correctly parses and validates the output
- [ ] `python -m pytest -q` passes
