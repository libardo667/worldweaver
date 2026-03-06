# Audit and normalize narrator/referee temperature assignment across all call sites

## Problem

`src/services/llm_service.py` has three temperature settings available via `settings`:
- `settings.llm_narrator_temperature` (`LLM_NARRATOR_TEMPERATURE`, default 0.8)
- `settings.llm_referee_temperature` (`LLM_REFEREE_TEMPERATURE`, default 0.2)
- `settings.llm_temperature` (`LLM_TEMPERATURE`, default 0.7) — legacy/generic

Most narrator and referee call sites in `llm_service.py` use the correct per-lane settings. However, `adapt_storylet_to_context` (line ~787) uses `settings.llm_temperature` for its narrator call — the legacy field — instead of `settings.llm_narrator_temperature`. This is an inconsistency that:

- Causes the sweep harness to inadvertently vary narrator temperature via `LLM_TEMPERATURE` rather than `LLM_NARRATOR_TEMPERATURE`
- Means the core per-turn adaptation call (the most frequent narrator call in a session) ignores the narrator-specific temperature setting
- Creates a hidden dependency on the legacy field that is easy to miss when reading the config or `.env`

A full audit is needed to confirm which call sites use which settings and to normalize any remaining inconsistencies.

## Proposed Solution

1. Grep all `_chat_completion_with_retry` calls in `llm_service.py` and `command_interpreter.py` for their `temperature=` argument. Classify each as:
   - `narrator` — should use `settings.llm_narrator_temperature`
   - `referee` — should use `settings.llm_referee_temperature`
   - `other` — justify separately (e.g., world-generation bootstrap calls that predate lane routing)

2. Fix any misassigned call sites. The confirmed fix is `adapt_storylet_to_context`: change `temperature=min(0.9, settings.llm_temperature)` to `temperature=max(0.0, min(1.2, float(settings.llm_narrator_temperature)))`, matching the clamp pattern used on other narrator sites.

3. For any call sites that legitimately use `settings.llm_temperature` (outside the narrator/referee lanes), add an inline comment explaining why — or migrate them to the appropriate per-lane setting.

4. Add a `# NOTE: uses llm_narrator_temperature / llm_referee_temperature` comment block near the top of `llm_service.py` documenting which settings govern which call categories. This makes the lane-temperature contract visible without requiring full file inspection.

5. Do not change `settings.llm_temperature` field definition in `config.py`. Keep it as a fallback for external integrations. Just ensure it is not used within the v3 narrator/referee pipeline.

## Files Affected

- `src/services/llm_service.py` — fix `adapt_storylet_to_context` and any other misassigned call sites; add lane-temperature comment block
- `src/services/command_interpreter.py` — audit narrator/referee call sites for temperature source

## Acceptance Criteria

- [ ] `adapt_storylet_to_context` reads `settings.llm_narrator_temperature` (not `settings.llm_temperature`).
- [ ] All narrator `_chat_completion_with_retry` calls in `llm_service.py` use `settings.llm_narrator_temperature`.
- [ ] All referee `_chat_completion_with_retry` calls in `llm_service.py` use `settings.llm_referee_temperature`.
- [ ] Any remaining use of `settings.llm_temperature` in the call chain has an inline justification comment.
- [ ] A lane-temperature comment block exists near the top of the LLM call surface in `llm_service.py`.
- [ ] `python scripts/dev.py quality-strict` passes.
