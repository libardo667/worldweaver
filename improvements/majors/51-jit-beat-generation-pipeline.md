# Replace batch storylet generation with just-in-time beat generation

## Problem

World creation currently generates **15 storylets in a single LLM call** (`generate_world_storylets` in `src/services/llm_service.py:982`), then generates a starting storylet in a second call (`generate_starting_storylet` at line 1088), then optionally runs auto-improvements (`run_auto_improvements` via `src/services/world_bootstrap_service.py:186`). This creates three compounding problems:

1. **Extreme latency**: The 15-storylet batch requires ~4000 output tokens of structured JSON. With reasoning models like DeepSeek R1, this takes 30–60+ seconds during onboarding — the user's first impression.

2. **Disconnected vignettes**: The 15 storylets are generated simultaneously with no narrative causality. They share variable keys by coincidence, not by design. There is no story spine, no rising tension, no character arc. The result is a **bag of interchangeable scenes** rather than a **sequence of causally connected events**.

3. **Wasted generation**: Most of the 15 storylets will never fire in a given session. The `pick_storylet_enhanced` function (`src/services/storylet_selector.py:166`) selects based on semantic similarity and requirements — many pre-generated storylets are permanently ineligible given the player's actual trajectory.

The adapt-on-delivery step (`adapt_storylet_to_context` in `llm_service.py:402`) attempts to compensate by rewriting pre-baked storylets to reference recent events, but this is cosmetic — it cannot transform a thematically unrelated scene into a causally connected continuation.

### Root cause

The engine treats story as a **pool of pre-generated content** selected at runtime (a storylet architecture), when the user's experience requires a **sequence of causally generated beats** where each scene flows from the previous one.

## Proposed Solution

Replace the batch-generate → select → adapt pipeline with a **world-bible + just-in-time (JIT) beat generation** approach:

### Phase 1: World Bible Generation (replaces 15-storylet batch)

Create a new function `generate_world_bible()` in `src/services/llm_service.py` that produces a lightweight **world bible** (~200–300 tokens) containing:
- 3–5 key locations (name + 1-line description)
- 3–4 NPCs (name + role + motivation)
- 1 central tension or mystery
- The player's entry point and initial situation

This replaces the `build_world_gen_system_prompt` call in `prompt_library.py:178` and the `generate_world_storylets` function. Estimated latency: 3–5 seconds.

Store the world bible in session state (via `AdvancedStateManager` or a new `world_bible` field on `SessionVars`).

### Phase 2: JIT Beat Generation (replaces pick + adapt)

Create a new function `generate_next_beat()` in `src/services/llm_service.py` that takes:
- The world bible (persistent context)
- Last 3–5 story event summaries (from `world_memory`)
- Current player state (location, key vars)
- Active story arc state (see Phase 3)

And produces **one scene**: narrative text + 2–3 choices with state changes.

This replaces the `pick_storylet_enhanced` → `adapt_storylet_to_context` two-step. The LLM sees **what just happened** and writes **what happens next**, creating natural causal flow.

### Phase 3: Story Arc Tracking

Add a lightweight `story_arc` dict to session state tracking:
- `act`: setup | rising_action | climax | resolution
- `tension`: the current central question or conflict
- `unresolved_threads`: list of things the player hasn't followed up on
- `turn_count`: number of beats so far

Update `story_arc` deterministically after each beat based on choice consequences. Feed it into beat generation to create narrative shape.

### Phase 4: Prompt Streamlining

Create a new compact prompt builder `build_beat_generation_prompt()` in `prompt_library.py` that includes:
- `NARRATIVE_VOICE_SPEC` (kept — essential for quality)
- World bible context (phase 1 output)
- Recent story context (from world memory)
- Story arc state (phase 3)
- Compact JSON output format spec (no exemplars needed after first gen)

Remove or deprecate: `build_world_gen_system_prompt`, `build_starting_storylet_prompt`, `build_adaptation_prompt`, and the large `QUALITY_EXEMPLARS` block from runtime prompts.

### Migration Strategy

Keep the existing storylet pool as a **fallback** layer. If JIT generation fails or times out, the system falls back to `pick_storylet_enhanced` on pre-generated content. The `generate_world_storylets` path remains available for the author API (`/author/generate-world`) but is no longer used for player onboarding.

## Files Affected

- `src/services/llm_service.py` — Add `generate_world_bible()` and `generate_next_beat()`; deprecate `generate_world_storylets` for onboarding path
- `src/services/prompt_library.py` — Add `build_world_bible_prompt()` and `build_beat_generation_prompt()`; keep existing builders for author/fallback paths
- `src/services/world_bootstrap_service.py` — Rewrite `bootstrap_world_storylets()` to generate bible instead of 15 storylets for onboarding; keep storylet path for author API
- `src/services/state_manager.py` — Add `story_arc` tracking dict to `AdvancedStateManager`
- `src/models/__init__.py` — Consider `world_bible` column on `SessionVars` (or encode in existing `vars` JSON)
- `src/api/game/story.py` — Update `api_next()` to call `generate_next_beat()` instead of `pick_storylet_enhanced` + `adapt_storylet_to_context` when a world bible is available
- `src/services/storylet_selector.py` — Retain as fallback; no destructive changes
- `src/services/prefetch_service.py` — Adapt prefetch to pre-generate beat stubs instead of pre-scoring storylets
- `src/config.py` — Add `enable_jit_beat_generation` feature flag (default `True`)

## Acceptance Criteria

- [ ] World creation completes in under 8 seconds (down from 30–60s)
- [ ] Player's first three beats form a causally connected narrative (each scene references or follows from the previous)
- [ ] World bible is persisted in session state and survives server restart
- [ ] Story arc state tracks act progression and updates after each beat
- [ ] JIT beat generation produces valid JSON with narrative text and 2–3 choices
- [ ] Existing storylet pool functions as fallback when JIT generation fails
- [ ] Author API `/author/generate-world` continues to work via the existing storylet path
- [ ] `python -m pytest -q` passes
- [ ] `npm --prefix client run build` passes

## Risks & Rollback

**Risk**: JIT generation may produce inconsistent world details across beats without the pre-established storylet pool enforcing location/NPC consistency.
**Mitigation**: The world bible acts as a persistent ground truth; each beat prompt includes it. World memory facts provide additional consistency anchoring.

**Risk**: Higher per-turn LLM cost (one generation call per turn instead of amortized batch).
**Mitigation**: JIT beats are shorter (~150–200 output tokens vs. 300+ for batch storylets + adaptation). Net token usage may be comparable or lower. Feature flag allows instant rollback to storylet pool.

**Risk**: The storylet-based infrastructure (spatial navigator, semantic selector, embedding service) becomes partially orphaned.
**Mitigation**: Keep these intact as the fallback layer and for the author API. This is an additive change, not a destructive one. Deprecation can happen incrementally after the JIT path proves stable.

**Rollback**: Set `enable_jit_beat_generation = False` in config to revert to the storylet pool pipeline. No schema migrations are destructive.
