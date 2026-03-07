# Batch world storylet generation to fix token-budget truncation

## Problem

`generate_world_storylets` in `src/services/llm_service.py` generates all N requested storylets in two single LLM calls — one referee call to produce all N contracts, then one narrator call to render them all as prose. This design has three compounding failure modes:

**Silent truncation.** The referee call is hardcapped at `max_tokens=min(2200, settings.llm_max_tokens)`. A single contract requires ~150-250 tokens of JSON. Requesting N=25 requires ~5000-6000 tokens of output — more than twice the cap. The model's JSON output is cut mid-array, and `_reduce_storylet_contracts` parses only the complete items before the truncation boundary. In practice, N=25 returns 2-3 usable contracts. The bootstrap endpoint returns `{"success": true, "storylets_created": 2}` with no error or warning. The harness cannot distinguish intentional minimalism from silent truncation.

**Quality degradation at high N.** Even if the token cap were raised, asking a model to generate 25 distinct, varied contracts in a single call produces repetitive output. Premises begin recycling after ~8-10 items because the model has no structural mechanism to enforce variety across a long output list.

**Downstream sweep invalidity.** The BFS projection tree samples from the storylet pool. With only 2 storylets, the tree can examine exactly 2 depth-1 candidates — trivially small, no meaningful referee scoring, and motif governance has nothing to vary across. Any sweep run bootstrapped with N=25 but receiving 2 is producing projection quality data on a degenerate pool. This invalidates projection hit rate, waste rate, clarity distribution, and narrator reuse metrics for all configs in that sweep.

**Bootstrap gate is too loose.** The harness bootstrap gate only checks `storylets_created > 0`, which passes with 2 and gives no indication that 23 of 25 requested storylets were silently dropped.

## Proposed Solution

### 1. Batched generation in `generate_world_storylets`

Replace the single referee + narrator call pair with a batched loop. A `batch_size` of 6 is recommended:

- Generate the world bible once (unchanged).
- Loop until `target_count` storylets are collected, requesting `batch_size` per iteration.
- Pass `existing_titles` to each referee call so the model can explicitly avoid repeating premises already committed in prior batches. This is the primary quality mechanism.
- On any batch failure, log and continue — partial results are usable. Do not abort the full generation on a single batch failure.
- The referee token budget per batch: `min(2200, settings.llm_max_tokens)` remains appropriate for batches of 6 (6 × ~250 tokens = ~1500 tokens, comfortable).
- The narrator token budget per batch: `min(3000, settings.llm_max_tokens)` for batches of 6.

```
target: 25 storylets
batch_size: 6
batches needed: ceil(25/6) = 5 referee calls + 5 narrator calls
existing overhead: +1 world bible call
total calls: 11 (vs. current 3)
```

The additional LLM calls are acceptable at bootstrap time — bootstrap is a one-time per-session cost.

### 2. Surface `existing_titles` in the referee prompt

Add a field to the referee world generation prompt:
```json
{
  "existing_titles": ["Title A", "Title B", ...],
  "instruction": "Generate storylets whose premises and titles are distinct from the existing_titles list."
}
```

This is a prompt-only change — no schema contract breaks.

### 3. Tighten the harness bootstrap gate

In `playtest_harness/long_run_harness.py`, after reading `storylets_created` from the bootstrap result, add a proportional check:

```python
requested = config.storylet_count
created = int(bootstrap_result.get("storylets_created", 0) or 0)
if created < max(5, requested // 2):
    raise RuntimeError(
        f"bootstrap storylet gate failed: requested={requested}, created={created} "
        f"(less than 50% of target — likely token truncation)"
    )
```

This catches the silent-truncation failure mode without requiring exact delivery (some batches may legitimately fail on adversarial inputs).

### 4. No change to the bootstrap API response shape

The `bootstrap_world_storylets` function in `world_bootstrap_service.py` already returns `storylets_created` from `save_result.get("added", ...)`. No changes needed there — the fix is upstream in `generate_world_storylets`.

## Files Affected

- `src/services/llm_service.py` — refactor `generate_world_storylets` to loop in batches of 6; pass `existing_titles` in each referee prompt; per-batch narrator render
- `src/services/prompt_library.py` — add `existing_titles` parameter to `build_world_storylets_referee_prompt` (or equivalent prompt-build helper) if one exists; otherwise inline in `generate_world_storylets`
- `playtest_harness/long_run_harness.py` — tighten bootstrap gate to check `created >= max(5, requested // 2)`

## Acceptance Criteria

- [ ] `generate_world_storylets(count=25)` returns at least 20 storylets (≥ 80% delivery rate) in a live call.
- [ ] `generate_world_storylets(count=8)` returns exactly 8 storylets (single batch, same behavior as today for small counts).
- [ ] Storylet titles across a 25-count generation are distinct (no exact duplicates).
- [ ] Bootstrap harness gate raises `RuntimeError` when `storylets_created < max(5, requested // 2)`.
- [ ] No existing test is broken — the function signature and return type are unchanged.
- [ ] `python scripts/dev.py quality-strict` passes.
