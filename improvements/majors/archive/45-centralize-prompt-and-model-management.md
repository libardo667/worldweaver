# Centralize prompt and model management

## Problem
In the initial iterations, LLM prompts were hardcoded inline inside service files (`llm_service.py`, `command_interpreter.py`, `story_deepener.py`). This led to:
1. **Inconsistent Quality**: Inline prompts lacked unified narrative voice guidance and few-shot exemplars, causing storylets to sometimes degrade into generic or un-game-like responses.
2. **Scattered Logic**: Modifying the “game voice” required hunting down 9 distinct prompt sites across 3 files.
3. **Model Opaqueness**: The specific LLM model was hardcoded or buried in `.env` without offering transparency to the user regarding cost or quality. If a user wanted to change models, it required a server restart.

## Proposed Solution
Extract all prompt strings and model choices into centralized registry and library files, and expose model selection via a runtime API endpoints for the client UI.

1. **`prompt_library.py`**: Central source of truth for all system and user prompt generation. Includes explicit `NARRATIVE_VOICE_SPEC` (2nd person, present tense), `ANTI_PATTERNS`, and `QUALITY_EXEMPLARS` for few-shot learning.
2. **`model_registry.py`**: A registry of 10+ supported OpenRouter models, detailing pricing tiers, context windows, and estimated 10-turn session costs.
3. **API Integration**: Re-wire `llm_service.py`, `command_interpreter.py`, and `story_deepener.py` to call `prompt_library` builder functions.
4. **Settings API**: Add `GET /api/models`, `GET /api/model`, and `PUT /api/model` to `settings_api.py` allowing dynamic runtime model switching.
5. **UI Integration**: Add a Model Selector dropdown or modal to the React `topbar` component to visually display the current model, its per-session cost estimate, and allow hot-swapping.

## Files Affected
- `src/services/prompt_library.py` (Created)
- `src/services/model_registry.py` (Created)
- `tests/service/test_prompt_and_model.py` (Created)
- `src/api/game/settings_api.py` (Created)
- `src/api/game/__init__.py` (Modified)
- `src/services/llm_service.py` (Modified)
- `src/services/command_interpreter.py` (Modified)
- `src/services/story_deepener.py` (Modified)
- `client/src/App.tsx` (Topbar model selector integration)

## Acceptance Criteria
- [x] All 9 backend prompt sites utilize `prompt_library.py` builders.
- [x] Model cost estimations are accurately calculated for at least 5 supported OpenRouter models.
- [x] Backend test suite passes without regressions (with AI disabled / fallback mode).
- [x] HTTP APIs route requests to switch models at runtime without requiring a server reboot.
- [x] UI Topbar includes a model selector that pulls from `GET /api/models`.
- [x] UI Topbar displays cost estimates per session to the player.
- [x] Selecting a new model in the UI invokes `PUT /api/model` and immediately applies the change.

## Risks & Rollback
- **Risk**: New prompts increase token consumption and break context limits.
  - **Mitigation**: Monitored via OpenRouter dashboard; fallback to older inline prompts via git revert if necessary.
- **Risk**: Model switching runtime state conflicts across simultaneous users.
  - **Mitigation**: WorldWeaver is currently single-tenant by design.
- **Rollback**: To undo these changes, `git revert` the commits affecting the service files and delete the two new module files.
