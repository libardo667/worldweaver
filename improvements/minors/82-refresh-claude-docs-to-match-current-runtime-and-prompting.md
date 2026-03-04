# Refresh CLAUDE.md to match current runtime, model selection, and prompt pipeline reality

## Problem

`CLAUDE.md` is stale in several areas (router/module map, linting/tooling
status, runtime command surface), which can mislead contributors and agents.

## Proposed Solution

Update `CLAUDE.md` to reflect the current codebase and workflows:

1. Correct API/router structure and key service ownership.
2. Document current model selection path and active LLM command surface.
3. Align command references with `scripts/dev.py`.
4. Clarify current fast-lane/slow-lane code paths and relevant feature flags.

## Files Affected

- `CLAUDE.md`
- `README.md` (only if command cross-links need alignment)

## Acceptance Criteria

- [ ] `CLAUDE.md` references current API module structure and service ownership.
- [ ] Model selection and prompt pipeline descriptions match current code paths.
- [ ] Command examples are aligned with `scripts/dev.py`.
- [ ] No stale references to removed files or workflows remain.

