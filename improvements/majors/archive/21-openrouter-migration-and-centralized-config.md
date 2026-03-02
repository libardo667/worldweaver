# OpenRouter Migration and Centralized Configuration

## Problem

The project was heavily OpenAI-centric, requiring an `OPENAI_API_KEY` and defaulting to OpenAI models even when using OpenRouter as a base URL. Furthermore, dozens of hyper-parameters (temperature, max_tokens, timeouts) and system settings (spatial radius, cache TTL) were hardcoded across multiple service files (`llm_service.py`, `game_logic.py`, `spatial_navigator.py`), making configuration rigid and error-prone.

## Proposed Solution

1.  **Centralized Configuration**: Introduced `src/config.py` using `pydantic-settings`. This subsystem loads all environment variables into a typed `Settings` object with sensible defaults.
2.  **OpenRouter-First Integration**: Refactored `src/services/llm_client.py` to support `OPENROUTER_API_KEY` and prioritize it over other keys. Added a curated list of reputable OpenRouter models.
3.  **Model Defaults**: Set `deepseek/deepseek-r1` as the default model for all chat completions due to its strong JSON performance and cost-efficiency.
4.  **Dynamic Service Parameters**: Modified `src/services/llm_service.py` to pull all generation parameters (tokens, temperature, timeouts) from the centralized `settings` instead of using literals.

## Files Affected

- `src/config.py` (NEW)
- `src/services/llm_client.py`
- `src/services/llm_service.py`
- `tests/diagnostic/test_llm_config.py` (NEW)

## Acceptance Criteria

- [x] `OPENROUTER_API_KEY` is recognized and prioritized.
- [x] All hardcoded LLM parameters are replaced by `settings` references.
- [x] `deepseek/deepseek-r1` is the default model.
- [x] Configuration can be overridden via `.env` or environment variables without code changes.
- [x] Diagnostic tests verify API key precedence and setting loading.

## Risks & Rollback

- **Dependency Risk**: Added `pydantic-settings` to the environment. If it fails to load, `src/config.py` will raise an `ImportError`. 
- **Rollback**: To revert, restore `llm_client.py` and `llm_service.py` to their previous versions and delete `src/config.py`.
