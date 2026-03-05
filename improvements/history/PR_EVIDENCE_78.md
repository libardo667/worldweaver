# PR Evidence: Minor 78 - Unify LLM JSON Extraction and Schema Validation

## Item

`improvements/minors/archive/78-unify-llm-json-extraction-and-schema-validation.md`

## Scope

Unified JSON extraction and schema-validation behavior across generation and
interpretation paths to prevent parser drift and inconsistent fallback handling.

## What Changed

| File | Change |
|------|--------|
| `src/services/llm_json.py` | Added centralized helpers: JSON extraction, object/array coercion, schema validation, and machine-readable error categories via `LLMJsonErrorCategory`. |
| `src/services/llm_service.py` | Replaced duplicated extraction logic with shared `llm_json` helper usage; introduced category-aware fallback logging; applied shared schema validator for storylet payload model. |
| `src/services/command_interpreter.py` | Replaced direct `json.loads` response parsing with shared helper; added consistent machine-readable warning categories for malformed JSON fallback paths. |
| `tests/service/test_llm_service.py` | Added assertion for machine-readable JSON error category logging on malformed model output. |
| `tests/service/test_command_interpreter.py` | Added assertion that malformed model JSON surfaces standardized warning category in reasoning metadata. |
| `improvements/minors/archive/78-unify-llm-json-extraction-and-schema-validation.md` | Marked complete and archived with execution evidence. |
| `improvements/ROADMAP.md` | Marked minor 78 complete and updated execution-order notes. |

## Why This Matters

Before this change, JSON extraction and validation logic diverged between
services. That makes behavior brittle and inconsistent when LLM outputs are
malformed or wrapped. A shared parser/validator:

- reduces drift and duplicate bugfix effort,
- standardizes fallback/error classification for operations and telemetry,
- improves safety by ensuring malformed JSON does not escape as uncaught errors
  in core generation/interpretation paths.

## Quality Gate Evidence

### Gate 1: Contract Integrity

- No API route/path/payload shape changes.

### Gate 2: Correctness

- `python -m pytest -q tests/service/test_llm_service.py tests/service/test_command_interpreter.py` -> pass
- `python -m pytest -q tests/api/test_action_endpoint.py tests/api/test_game_endpoints.py` -> pass
- `python -m pytest -q` -> `528 passed, 14 warnings`

### Gate 3: Build and Static Health

- `python -m ruff check src/api src/services src/models main.py` -> pass
- `python -m black --check src/api src/services src/models main.py` -> pass
- `python scripts/dev.py lint-all` -> pass
- `python scripts/dev.py gate3` -> pass
- `npm --prefix client run build` -> pass

### Gate 5: Operational Safety

- Rollback path: revert this PR to restore prior per-service JSON parsing logic.
- No schema migration or persistent state shape change introduced.

## Residual Risk

- Additional LLM output variants may still appear in production; category-based
  error surfacing now makes those variants easier to detect and harden with
  targeted follow-up tests.
