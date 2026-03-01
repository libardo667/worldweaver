# Extract hardcoded values into a central configuration

## Problem

Dozens of magic numbers and strings are scattered across the services:

- `game_logic.py` line 64: minimum eligible storylets = `3`
- `game_logic.py` line 68: auto-generate count = `5`
- `llm_service.py`: temperature `0.7`/`0.8`, max_tokens `1000`/`2500`/`4000`,
  model `"gpt-4o"` repeated in 3+ places
- `story_deepener.py` line 258: bridge limit = `3`, coherence threshold = `0.6`
- `state_manager.py` line 529: cache TTL = `30` seconds
- `location_mapper.py` line 232: spiral search radius = `20`
- `spatial_navigator.py` line 344: max radius = `20`

Changing any of these requires editing deep service code and risking
regressions.

## Proposed Solution

1. Create `src/config.py` using `pydantic-settings` (already a dependency)
   with a `Settings` class that reads from environment variables and `.env`,
   with sensible defaults matching current hardcoded values.
2. Group settings by domain: `llm_model`, `llm_temperature`,
   `llm_max_tokens`, `min_eligible_storylets`, `auto_generate_count`,
   `cache_ttl_seconds`, `spatial_max_radius`, `bridge_limit`,
   `coherence_threshold`.
3. Replace each hardcoded value with a reference to `settings.<field>`.
4. Document the new environment variables in `CLAUDE.md`.

## Files Affected

- `src/config.py` (new)
- `src/services/game_logic.py`
- `src/services/llm_service.py`
- `src/services/story_deepener.py`
- `src/services/state_manager.py`
- `src/services/location_mapper.py`
- `src/services/spatial_navigator.py`
- `CLAUDE.md`

## Acceptance Criteria

- [ ] No numeric/string literals remain for the values listed above
- [ ] `Settings` class has typed fields with defaults for every extracted
      value
- [ ] Setting `LLM_MODEL=gpt-3.5-turbo` in `.env` changes the model used
      everywhere
- [ ] All existing tests still pass with no env vars set (defaults match
      prior behaviour)

## Risks & Rollback

If `pydantic-settings` import fails (unlikely — it's already in
`requirements.txt`), revert the new file and the import lines. Every
default matches the old hardcoded value, so behaviour is unchanged unless
env vars are set.
