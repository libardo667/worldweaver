# Unify LLM JSON extraction and schema validation across generation and interpretation paths

## Disposition

Completed and archived on March 4, 2026.

## Problem

JSON parsing/validation logic is currently duplicated across services (for
example `src/services/llm_service.py` and
`src/services/command_interpreter.py`), increasing drift risk and inconsistent
failure handling.

## Proposed Solution

Create a shared utility for model-output parsing:

1. Add a centralized JSON extraction helper that handles code fences, malformed
   wrappers, and object/list coercion.
2. Add schema-based validation helpers (Pydantic models where available) with
   standardized error surfaces.
3. Migrate generation and action-interpretation paths to use the shared helper.
4. Keep fallback behavior explicit and consistent across callers.

## Files Affected

- `src/services/llm_service.py`
- `src/services/command_interpreter.py`
- `src/services/llm_json.py` (new)
- `tests/service/test_llm_service.py`
- `tests/service/test_command_interpreter.py`

## Acceptance Criteria

- [x] Shared JSON extraction utility is used by both `llm_service` and
      `command_interpreter`.
- [x] Schema validation failures produce consistent, machine-readable error
      categories.
- [x] Malformed model JSON falls back safely without uncaught exceptions.
- [x] Existing storylet generation and action interpretation tests pass.

## Execution Evidence (March 4, 2026)

- Added shared utility module:
  - `src/services/llm_json.py`
- Migrated `llm_service` and `command_interpreter` to use centralized JSON
  extraction/parsing helpers.
- Added standardized machine-readable parse/validation categories via
  `LLMJsonErrorCategory` and `LLMJsonError`.
- Added schema validation helper (`validate_with_model`) and applied it to
  storylet payload validation.
- Added/updated tests:
  - `tests/service/test_llm_service.py`
  - `tests/service/test_command_interpreter.py`
- Validation:
  - `python -m pytest -q` -> pass
  - `python scripts/dev.py gate3` -> pass
  - `npm --prefix client run build` -> pass
