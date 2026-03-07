# Stratify sweep parameter axes by model lane

## Problem

The current sweep harness (`playtest_harness/parameter_sweep.py`) represents temperature as a single shared axis (`llm_temperature`) that is injected into the backend as `LLM_TEMPERATURE`. However, the v3 architecture maintains distinct temperature settings per lane:

- `LLM_NARRATOR_TEMPERATURE` (default 0.8) — used by scene narrator calls in `llm_service.py`
- `LLM_REFEREE_TEMPERATURE` (default 0.2) — used by planner/referee audit calls in `llm_service.py`

The legacy `LLM_TEMPERATURE` setting (`settings.llm_temperature`) is currently used only by `adapt_storylet_to_context` at `llm_service.py:787`, which is itself a narrator-role call. All other narrator and referee call sites already use the correct per-lane settings.

This creates two concrete problems:

1. **The sweep's temperature variation is lane-blind.** Sweeping `llm_temperature` affects only the `adapt_storylet_to_context` narrator path, while the referee audit and narrator rewrite pass each use their own hardcoded `.env` defaults (`LLM_NARRATOR_TEMPERATURE=0.8`, `LLM_REFEREE_TEMPERATURE=0.2`). You cannot ask "narrator at 0.9, referee at 0.15" vs "narrator at 0.5, referee at 0.3" — which is precisely the question the three-lane vision requires.

2. **The main per-turn narrator call uses the wrong temperature setting.** `adapt_storylet_to_context` reads `settings.llm_temperature` instead of `settings.llm_narrator_temperature`. This is an inconsistency relative to every other narrator call site in the same file.

The sweep data confirms this: all runs in the full dark fantasy sweep reported different `llm_temperature` values in their parameter records, but the narrator and referee were running at fixed `.env` defaults throughout — making the temperature axis a measurement of noise, not a controlled variable.

## Proposed Solution

### Phase 1: Fix the narrator call site inconsistency

1. In `llm_service.py`, change `adapt_storylet_to_context` to use `settings.llm_narrator_temperature` instead of `settings.llm_temperature`. Apply the same clamp already used on other narrator sites: `max(0.0, min(1.2, float(settings.llm_narrator_temperature)))`.
2. Document `settings.llm_temperature` as a legacy/generic fallback that is no longer used in the core narrative pipeline. It may remain in config for external integrations that rely on `LLM_TEMPERATURE` but should not appear in narrator or referee calls.

### Phase 2: Split SweepParameterSet into per-lane axes

1. Replace `llm_temperature: float` in `SweepParameterSet` (in `parameter_sweep.py`) with:
   - `llm_narrator_temperature: float`
   - `llm_referee_temperature: float`
2. Update `generate_phase_a_parameter_sets` to sample both axes independently via Latin hypercube. Use separate ranges per lane:
   - Narrator: `(0.4, 1.2)` — creative range appropriate for prose generation
   - Referee: `(0.0, 0.5)` — precision range appropriate for structured JSON evaluation
3. Update `SweepParameterSet.env_overrides()` to call `build_parameter_env_overrides_from_values` with `llm_narrator_temperature` and `llm_referee_temperature` instead of `llm_temperature`.

### Phase 3: Update the env override builder

1. In `long_run_harness.py`, update `build_parameter_env_overrides_from_values` to accept and inject `llm_narrator_temperature` and `llm_referee_temperature` as `LLM_NARRATOR_TEMPERATURE` and `LLM_REFEREE_TEMPERATURE` env vars respectively.
2. Remove injection of `LLM_TEMPERATURE` from the sweep path. The legacy `LLM_TEMPERATURE` env var should not be set by sweep runs to avoid masking per-lane settings.
3. Existing callers that pass `llm_temperature=` should still work through the signature but that parameter should no longer be written to the override dict if per-lane equivalents are provided.

### Phase 4: Update sweep summaries and manifests

1. Update `parameters` field in per-run and phase summary JSON to record `llm_narrator_temperature` and `llm_referee_temperature` instead of (or alongside) `llm_temperature`.
2. Update `LaneBudgetVariant` to optionally include `llm_narrator_temperature` and `llm_referee_temperature` overrides so lane-matrix and per-lane-temp axes can be independently composed.
3. Update manifest schema docs and any existing ranking code that reads `parameters.llm_temperature` to use the per-lane fields.

### Phase 5: Test hardening

1. Add tests in `tests/integration/test_parameter_sweep_phase_a.py` verifying that generated parameter sets contain `llm_narrator_temperature` and `llm_referee_temperature` keys and that they fall within their declared ranges.
2. Add tests verifying `env_overrides()` injects `LLM_NARRATOR_TEMPERATURE` and `LLM_REFEREE_TEMPERATURE` but does not inject `LLM_TEMPERATURE`.
3. Add a regression test verifying `adapt_storylet_to_context` reads `llm_narrator_temperature` (confirm via settings mock, not live LLM call).

## Files Affected

- `src/services/llm_service.py` — fix `adapt_storylet_to_context` temperature source
- `playtest_harness/parameter_sweep.py` — replace `llm_temperature` axis with per-lane axes
- `playtest_harness/long_run_harness.py` — update `build_parameter_env_overrides_from_values`
- `tests/integration/test_parameter_sweep_phase_a.py` — per-lane axis shape and range tests
- `tests/service/test_prompt_and_model.py` — narrator temp source regression test

## Acceptance Criteria

- [ ] `adapt_storylet_to_context` uses `settings.llm_narrator_temperature`, not `settings.llm_temperature`.
- [ ] `SweepParameterSet` has `llm_narrator_temperature` and `llm_referee_temperature` fields; `llm_temperature` is removed.
- [ ] `generate_phase_a_parameter_sets` samples narrator and referee temperatures as independent LHS axes with separate ranges.
- [ ] Sweep env overrides inject `LLM_NARRATOR_TEMPERATURE` and `LLM_REFEREE_TEMPERATURE`; `LLM_TEMPERATURE` is not injected by the sweep path.
- [ ] Phase A/B summary JSON `parameters` field includes `llm_narrator_temperature` and `llm_referee_temperature`.
- [ ] Integration tests pass verifying axis shape, range, and env override key correctness.
- [ ] `python scripts/dev.py quality-strict` passes.
- [ ] Existing sweep consumers receiving summary JSON are not broken (additive field change only where the old `llm_temperature` key is either preserved as an alias or consumers are updated).

## Risks & Rollback

- Risk: Widening the narrator temperature range (0.4–1.2) substantially expands the hyperparameter search space, increasing Phase A sweep cost and runtime.
- Risk: Removing `LLM_TEMPERATURE` injection could break any integration that relies on the legacy env var outside the sweep path.
- Rollback: Revert `SweepParameterSet` to single `llm_temperature` field and revert `build_parameter_env_overrides_from_values` to inject `LLM_TEMPERATURE`. The narrator call site fix (`adapt_storylet_to_context`) is independently safe and does not need to be reverted.
- Rollback: The per-lane env var injection is additive at the backend level — reverting the sweep to inject `LLM_TEMPERATURE` will simply fall back to the `.env` defaults for narrator and referee, restoring prior behavior.
