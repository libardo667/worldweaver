# Batch B Runtime Services Slice 2

Date: `2026-03-06`
Status: `completed`

## Scope
- Further simplify runtime service flow by avoiding auto-improvement execution when all improvement features are disabled.
- Reduce default-path coupling to dormant `story_smoother` / `story_deepener` workflows.

## Changes
1. Added default-path short-circuit for auto-improvement:
- `src/services/storylet_ingest.py`
  - `run_auto_improvements(...)` now returns `None` when both:
    - `settings.enable_story_smoothing == false`
    - `settings.enable_story_deepening == false`

2. Added same guard to generation entrypoints:
- `src/services/game_logic.py`
  - `ensure_storylets(...)` auto-improvement path now runs only when at least one improvement flag is enabled.
  - `auto_populate_storylets(...)` auto-improvement path now runs only when at least one improvement flag is enabled.
  - explicit skip log added for visibility.

3. Added coverage for disabled-path behavior:
- `tests/service/test_decomposed_functions.py`
  - verifies `run_auto_improvements(...)` returns `None` and does not call improvement hooks when both flags are disabled.

## Guardrail Verification
Commands:
- `ruff check src/services/storylet_ingest.py src/services/game_logic.py tests/service/test_decomposed_functions.py`
- `pytest -q tests/service/test_decomposed_functions.py tests/service/test_storylet_ingest.py tests/integration/test_author_pipeline_transactions.py`
- `python scripts/dev.py quality-strict`

Results:
- Lint: pass
- Targeted tests: `18 passed`
- Full strict gate: pass (`581 passed`; warning budget unchanged)

## Batch B Impact
- Advances `runtime_services` simplify track by making dormant improvement paths truly inactive in default configuration.
- Keeps behavior opt-in through explicit flags and preserves existing author/game contracts.
