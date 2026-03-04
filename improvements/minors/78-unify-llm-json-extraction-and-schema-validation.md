# Unify LLM JSON extraction and schema validation across generation and interpretation paths

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
- `src/models/schemas.py`
- `src/services/llm_json.py` (new)
- `tests/service/test_llm_service.py`
- `tests/service/test_command_interpreter.py`

## Acceptance Criteria

- [ ] Shared JSON extraction utility is used by both `llm_service` and
      `command_interpreter`.
- [ ] Schema validation failures produce consistent, machine-readable error
      categories.
- [ ] Malformed model JSON falls back safely without uncaught exceptions.
- [ ] Existing storylet generation and action interpretation tests pass.

