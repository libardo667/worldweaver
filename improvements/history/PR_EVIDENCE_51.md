# PR Evidence: Major 51 — JIT Beat Generation Pipeline

## Branch
`major/51-jit-beat-generation-pipeline`

## Atomic Minor Breakdown

| Minor | File(s) | Change |
|-------|---------|--------|
| 72 | `src/config.py` | Added `enable_jit_beat_generation: bool = False` (env: `WW_ENABLE_JIT_BEAT_GENERATION`) |
| 73 | `src/services/prompt_library.py` | Added `build_world_bible_prompt()`, `build_beat_generation_prompt()`, `_WORLD_BIBLE_OUTPUT_SCHEMA`, `_BEAT_OUTPUT_SCHEMA` |
| 73 | `src/services/llm_service.py` | Added `generate_world_bible()`, `generate_next_beat()`, `_fallback_world_bible()`, `_fallback_beat()` |
| 75 | `src/services/state_manager.py` | Added `set_world_bible()`, `get_world_bible()`, `get_story_arc()`, `advance_story_arc()` |
| 75 | `src/services/world_bootstrap_service.py` | Added JIT path (bible + starting storylet) before classic 15-storylet path; full fallback on error |
| 75 | `src/api/game/story.py` | Added JIT beat path in `api_next` (calls `generate_next_beat` when flag on + bible exists); falls back to classic path |

## Why

Replaces the batch 15-storylet generation (30–60s latency, no narrative causality) with a lean world bible (3–8s) + per-turn JIT beat generation. Each beat is generated from what just happened so scenes flow causally instead of being random disconnected vignettes.

## Quality Gate Evidence

### Gate 1: Contract Integrity ✅
- `WW_ENABLE_JIT_BEAT_GENERATION=false` (default): zero runtime behaviour change
- JIT path in `api_next` only activates when flag is on AND `state_manager.get_world_bible()` returns a dict
- Classic storylet path code is unchanged and still exercised by all existing tests

### Gate 2: Correctness ✅
```
python -m pytest -q → 479 passed, 13 warnings in 13.29s (exit 0)
```
One additional warning vs pre-change (13 vs 12) — harmless Pydantic event loop warning from existing test infrastructure.

### Gate 3: Build and Static Health ✅
```
npm --prefix client run build → built in 684ms (exit 0)
```

### Gate 5: Operational Safety ✅
- **Feature flag default**: `False` — no production behaviour change until opt-in
- **Rollback**: Set `WW_ENABLE_JIT_BEAT_GENERATION=false` or remove env var
- **Fallbacks**: Both `generate_world_bible()` (bootstrap) and `generate_next_beat()` (api_next) have deterministic in-process fallbacks; neither raises to the caller
- **No migrations**: All new state stored in existing `variables` JSON column with `_` prefixed keys

## Architecture Summary

```
BEFORE:
  bootstrap → generate_world_storylets() → 15 storylets (30-60s)
  api_next  → pick_storylet_enhanced() → adapt_storylet_to_context() (2 LLM calls)

AFTER (when WW_ENABLE_JIT_BEAT_GENERATION=true):
  bootstrap → generate_world_bible()   → 1 world bible dict (3-8s)
            → generate_starting_storylet() → 1 opening beat
  api_next  → generate_next_beat(bible, recent_events, state, arc) → 1 causal beat
```

## Story Arc Progression

Acts promote deterministically via turn count thresholds:
- setup (turns 0-2) → rising_action (3-7) → climax (8-13) → resolution (14+)
- Thresholds are module-level constants, easily tunable in v2
