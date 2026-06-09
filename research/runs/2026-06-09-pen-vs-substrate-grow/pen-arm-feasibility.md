# Pen-arm feasibility sweep (2026-06-09) — choosing the swap foreign pens

Method note: speed is a **feasibility floor, not a selection axis** (the replay is offline + deterministic,
so tok/s sets wall-clock, never the pen's choices; and matching the home pen's speed would bias toward
same-family pens — the one thing a foreign pen must not be). So this sweep is used to (a) check the premise
that haiku-4.5 is too slow, and (b) pick ≥2 **different-family** pens above a wall-clock tolerance.
Reproduce: `pen_throughput_bench.py` (point-in-time; serving speeds vary by load/hour).

## Result table (pulse-sized JSON generation, median of 2; arm-wall = 1300 sequential pulses)

| model | family | tok/s | s/call | arm-wall(h) | vs home | JSON |
|---|---|---|---|---|---|---|
| google/gemini-3-flash-preview | Google (HOME) | 52.9 | 1.75 | 0.6 | 1.00x | ok |
| google/gemini-3.5-flash | Google (same-family trap) | 130.3 | 3.81 | 1.4 | 2.46x | ? |
| **anthropic/claude-haiku-4.5** | **Anthropic (pre-reg foreign)** | **51.9** | **2.02** | **0.7** | **0.98x** | **ok** |
| openai/gpt-5-mini | OpenAI | 38.7 | 11.56 | 4.2 | 0.73x | ? |
| openai/gpt-5-nano | OpenAI | 58.1 | 7.71 | 2.8 | 1.10x | ? |
| deepseek/deepseek-v4-flash | DeepSeek | 42.7 | 2.84 | 1.0 | 0.81x | ok |
| meta-llama/llama-4-maverick | Meta | 58.7 | 0.85 | 0.3 | 1.11x | ok |
| meta-llama/llama-4-scout | Meta (small) | 72.3 | 0.80 | 0.3 | 1.37x | ok |
| mistralai/mistral-small-2603 | Mistral | 75.5 | 0.85 | 0.3 | 1.43x | ok |
| mistralai/ministral-8b-2512 | Mistral (small) | 67.1 | 1.49 | 0.5 | 1.27x | ok |
| amazon/nova-2-lite-v1 | Amazon | 92.9 | 1.00 | 0.4 | 1.76x | ok |
| qwen/qwen3-235b-a22b | Qwen | 68.5 | 6.54 | 2.4 | 1.29x | ok |
| x-ai/grok-4-fast | xAI | — | — | — | — | (id 404) |
| cohere/command-r-08-2024 | Cohere | 45.0 | 1.29 | 0.5 | 0.85x | ok |

## Findings

1. **The premise didn't replicate: claude-haiku-4.5 is ~the same speed as the home pen** here (0.98x,
   ~0.7h/arm), not "much slower." The earlier "haiku is slow" impression likely came from a *different*
   workload (extended thinking, longer generations, or busier serving). → **Don't drop the pre-reg arm for
   speed on this evidence** — but confirm on the REAL pulse prompt (bigger than this 500-tok proxy) before
   locking, since the impression came from somewhere.
2. **The actually-slow ones are OpenAI's reasoning models** (gpt-5-mini 4.2h, -nano 2.8h) and Qwen-235b
   (2.4h) — latency from hidden thinking / big MoE. Not our arms anyway.
3. **The same-family "trap" is real but not via speed-matching** — gemini-3.5-flash is *faster*, not
   matched; it's disqualified for being Google, full stop, regardless of speed.
4. **JSON gate is a proxy here.** The "?" rows (gemini-3.5, both gpt-5) didn't emit clean pulse-JSON in the
   cap (reasoning wrappers / truncation). Confirm pulse-contract adherence on the REAL prompt via a
   `replay_run` dry-run per finalist before locking — fast-but-can't-emit-the-contract is useless.

## Recommended swap arms (pre-data; for Mr. Review amendment)

- **Home / maturation:** `google/gemini-3-flash-preview` (Google). [unchanged]
- **Foreign #1:** `anthropic/claude-haiku-4.5` (Anthropic) — **keep**; feasible (~0.7h/arm), json-ok.
- **Foreign #2:** `deepseek/deepseek-v4-flash` (DeepSeek) — maximally distant lineage, json-ok, ~1.0h/arm.
- **Optional Foreign #3:** `meta-llama/llama-4-maverick` (Meta, open-weights) — json-ok, ~0.3h/arm.

→ Four distinct families (Google · Anthropic · DeepSeek · Meta) make the swap a *strong* test; all are
feasible by wall-clock; selection is by family-distance, with speed only excluding the impractical.
