# Implement structure-first runtime storylet supply chain for sparse-context turns

## Problem

Runtime synthesis currently persists full generated storylets when context is
sparse (`_synthesize_runtime_storylets` in `src/services/storylet_selector.py`).
This couples background generation with immediate DB mutations and full prose
generation, which conflicts with the structure-first prefetch model in the
vision.

## Proposed Solution

Refactor runtime synthesis into a two-lane supply chain:

1. Generate and cache **storylet stubs** in background (premise, requires,
   choices, short notes, embeddings), not full narrated text.
2. Keep sparse-context trigger logic in selector, but consume prefetched stubs
   first.
3. Generate narration on demand only for the selected stub during turn commit.
4. Persist durable world mutations only on player-triggered commit, never during
   background prefetch.
5. Add runtime metrics for stub-hit rate, synthesis latency, and token usage.

## Files Affected

- `src/services/storylet_selector.py`
- `src/services/prefetch_service.py`
- `src/services/llm_service.py`
- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/services/runtime_metrics.py`
- `tests/service/test_storylet_selector.py`
- `tests/service/test_prefetch_service.py`

## Acceptance Criteria

- [ ] Sparse-context synthesis can produce cached stubs without writing full
      runtime storylets to the DB in background flows.
- [ ] Selected stubs are narrated on-demand at commit time.
- [ ] Background weaving remains additive and does not mutate persistent world
      state directly.
- [ ] Selector prefers prefetched stubs when available and falls back safely.
- [ ] Runtime metrics expose stub cache hit/miss and synthesis latency.
- [ ] `python -m pytest -q tests/service/test_storylet_selector.py
      tests/service/test_prefetch_service.py` passes.

## Risks & Rollback

Risk: poor stub quality can reduce narrative quality or increase fallback rates.

Rollback:

1. Keep existing full-runtime synthesis path behind a temporary fallback flag.
2. Roll back to current selector behavior if stub hit rate or coherence drops.
3. Retain instrumentation to compare old vs new pipeline before full cutover.

