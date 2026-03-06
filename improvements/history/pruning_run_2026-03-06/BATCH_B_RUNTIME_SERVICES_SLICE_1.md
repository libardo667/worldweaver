# Batch B Runtime Services Slice 1

Date: `2026-03-06`
Status: `completed`

## Scope
- Add explicit runtime flag control for story deepening.
- Keep behavior stable while making deepening opt-in for one-cycle validation.

## Changes
1. Added explicit flag:
- `src/config.py`
  - `enable_story_deepening` (`WW_ENABLE_STORY_DEEPENING`)
  - default: `false`

2. Gated deepening execution behind flag:
- `src/services/auto_improvement.py`
  - deepening now runs only when `run_deepening` and `settings.enable_story_deepening` are both true
  - logs explicit skip message when disabled

3. Propagated explicit deepening gate to callers:
- `src/services/storylet_ingest.py`
- `src/services/game_logic.py`

4. Added/updated tests for one-cycle policy:
- `tests/service/test_auto_improvement.py`
- `tests/service/test_decomposed_functions.py`

## Guardrail Verification
Commands:
- `ruff check src/config.py src/services/auto_improvement.py src/services/storylet_ingest.py src/services/game_logic.py tests/service/test_auto_improvement.py tests/service/test_decomposed_functions.py`
- `pytest -q tests/service/test_auto_improvement.py tests/service/test_decomposed_functions.py`
- `pytest -q tests/service/test_storylet_ingest.py tests/integration/test_author_pipeline_transactions.py tests/api/test_author_generate_world_confirmation.py`
- `python scripts/dev.py quality-strict`

Results:
- Lint: pass
- Targeted/service tests: `24 passed` (16 + 8)
- Full strict gate: pass (`580 passed`; warning budget unchanged)

## Batch B Impact
- Advances `runtime_services` simplify track with explicit feature-flag governance.
- Leaves `story_smoother` and `story_deepener` code present but makes deepening dormant by default.
