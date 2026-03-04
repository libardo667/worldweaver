# Switch default LLM model from DeepSeek R1 to a fluency-optimized model

## Problem

The default model in `src/config.py:24` is `deepseek/deepseek-r1` — a **reasoning-focused** model designed for math, code, and structured problem-solving. This is the wrong tool for WorldWeaver's primary workload (creative prose generation):

1. **Latency penalty**: R1 generates internal `<think>` chain-of-thought blocks before producing output. For creative writing tasks that don't benefit from step-by-step reasoning, this adds 5–15 seconds of pure overhead per call.

2. **Token waste**: The `<think>` tokens are counted toward usage and billing but produce no user-visible output. For a 15-storylet batch (the current world gen path), this can mean 2,000+ wasted thinking tokens.

3. **Prose quality mismatch**: R1's creative quality is rated `3` in the project's own `model_registry.py:66`. Models like Claude Sonnet 4 (`creative_quality: 5`), GPT-4o (`4`), or Aion 2.0 (`4`) produce better narrative prose at comparable or lower effective cost.

4. **Timeout risk**: The default `llm_timeout_seconds` is 15s (`config.py:29`). R1's reasoning overhead frequently pushes total generation time past this, causing retries or fallback to deterministic content.

The model registry (`src/services/model_registry.py`) already catalogues alternatives with explicit creative quality ratings. The runtime model selection infrastructure is already built (via `get_model()` in `llm_client.py` and the settings API). This fix is a one-line default change plus a sensible timeout adjustment.

## Proposed Solution

1. Change the default `llm_model` in `src/config.py` from `deepseek/deepseek-r1` to `openai/gpt-4o-mini`:
   - `creative_quality: 3` (same as R1)
   - Input: $0.15/M vs R1's $0.70/M (**78% cheaper input**)
   - Output: $0.60/M vs R1's $2.50/M (**76% cheaper output**)
   - No internal reasoning overhead — direct prose generation
   - 128K context window (vs R1's 64K)

2. Increase `llm_timeout_seconds` from `15` to `30` to accommodate larger generation requests without premature timeout.

3. Update the `creative_quality` rating for `deepseek/deepseek-r1` in `model_registry.py` from `3` to `2`, and add a note clarifying it is a reasoning model not optimized for creative prose.

Users who prefer R1 can still select it via the model selection UI — this only changes the out-of-box default.

## Files Affected

- `src/config.py` — Change `llm_model` default from `deepseek/deepseek-r1` to `openai/gpt-4o-mini`; change `llm_timeout_seconds` from `15` to `30`
- `src/services/model_registry.py` — Update `deepseek/deepseek-r1` entry: `creative_quality` from `3` to `2`, update notes to mention reasoning overhead

## Acceptance Criteria

- [ ] Default model is `openai/gpt-4o-mini` when no env override is set
- [ ] Default timeout is 30 seconds
- [ ] World generation completes without timeout on the default model
- [ ] Existing tests pass (`python -m pytest -q`)
- [ ] Storylet adaptation and action interpretation work on the new default
- [ ] Users can still override model via `LLM_MODEL` env var or settings API
