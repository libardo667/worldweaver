---
name: Update model registry with current OpenRouter models and pricing
type: minor
status: open
---

## Problem

`src/services/model_registry.py` lines 23–105 contain stale model IDs and outdated
pricing. Some entries (e.g. `google/gemini-3-flash-preview`, `qwen/qwen3.5-flash-02-23`,
`arcee-ai/trinity-large-preview:free`) may no longer exist on OpenRouter or have
changed IDs. Prices are from an earlier date and will be wrong for users trying to
estimate session costs.

## Work to do

1. Go to https://openrouter.ai/models and find current IDs + $/1M token pricing for:
   - At least two **free** models suitable for narrative prose
   - Two–three **budget** models ($0.10–$2/1M out)
   - One–two **standard** models ($3–$15/1M out)
   - One **premium** model (Claude Opus tier or equivalent)
2. Update `MODEL_REGISTRY` in `src/services/model_registry.py` with:
   - Correct `model_id` keys (exact OpenRouter slug)
   - Accurate `input_per_m` / `output_per_m` pricing
   - Realistic `creative_quality` ratings (1–5 scale, 5 = best prose)
   - Updated `context_window` values
   - Honest `notes` describing narrative fit
3. Verify each model ID actually exists by calling
   `GET https://openrouter.ai/api/v1/models` and confirming the slug appears.

## Files affected

- `src/services/model_registry.py` (MODEL_REGISTRY dict, lines 23–105)

## Acceptance criteria

- [ ] All model IDs in the registry exist on OpenRouter (verified via API)
- [ ] Pricing matches OpenRouter's published rates at time of update
- [ ] Free tier has at least one entry
- [ ] `list_available_models()` returns correct cost estimates
- [ ] No model ID is a `:free` variant that has since been removed
