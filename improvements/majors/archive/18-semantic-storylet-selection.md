# Replace requires-matching with semantic probability-based selection

## Problem

Storylet selection currently works by filtering on hard-coded `requires`
dicts and then doing a weighted random pick (`game_logic.pick_storylet`).
This is brittle — authors must know the exact variable names and values,
and it creates a rigid tree rather than the "field of narrative
possibilities" described in the vision.

The vision says: "Proximity in semantic space = probability of firing.
Story beats and character choices warp the probability field."

## Proposed Solution

1. **Create `src/services/semantic_selector.py`** with:
   - `compute_player_context_vector(state_manager, world_memory) -> list[float]`
     — builds a composite text from the player's current variables, recent
     choices, starting goal, and world history, then embeds it.
   - `score_storylets(context_vector, storylets) -> list[tuple[Storylet, float]]`
     — computes cosine similarity between the context vector and each
     storylet's embedding, applies a base probability floor (weak
     connections), and returns scored candidates.
   - `select_storylet(scored_candidates) -> Storylet` — weighted random
     selection where the weight = similarity score (not the old `weight`
     field, though that can act as a multiplier).

2. **Modify `pick_storylet`** in `game_logic.py` to:
   - Check if storylets have embeddings. If yes → use semantic selection.
   - If no → fall back to the existing `requires`-based logic (backward
     compatible).
   - This makes the transition gradual: as storylets get embedded, they
     automatically enter the semantic selection pool.

3. **The probability field concept**:
   - Base similarity score = `cosine_similarity(context, storylet_embedding)`
   - Floor probability = configurable minimum (e.g., 0.05) so distant
     storylets still have a small chance of firing
   - Multipliers: storylet `weight` field, recency penalty (don't repeat
     recently fired storylets), world-state alignment bonus

## Files Affected

- `src/services/semantic_selector.py` — new service
- `src/services/game_logic.py` — modify `pick_storylet` to use semantic path
- `src/services/embedding_service.py` — dependency (from improvement 16)
- `src/services/world_memory.py` — dependency (from improvement 17)
- `tests/service/test_semantic_selector.py` — new tests

## Acceptance Criteria

- [ ] `compute_player_context_vector` produces a valid embedding from game state
- [ ] `score_storylets` returns all storylets with non-zero scores
- [ ] Storylets semantically close to the player context score higher
- [ ] Distant storylets still have a non-zero floor probability
- [ ] `pick_storylet` uses semantic selection when embeddings are available
- [ ] `pick_storylet` falls back to requires-matching when embeddings are missing
- [ ] Recently fired storylets get a recency penalty
- [ ] Tests verify scoring, selection distribution, and fallback

## Risks & Rollback

The fallback to requires-matching means this is non-breaking. If semantic
selection produces poor results, disable it by clearing embeddings or
setting a config flag. The old path remains intact.
