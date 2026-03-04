# Promote player goal and arc tracking to a first-class runtime selection lens

## Problem

Goal/arc state exists in `AdvancedStateManager`, and semantic selector includes
some goal context, but goal influence is still uneven across selection, fact
retrieval, and beat progression paths.

Result: emergent turns can drift into disconnected vignettes instead of
maintaining a coherent arc spine.

## Proposed Solution

Standardize a goal/arc lens consumed by all major runtime systems:

1. Define a canonical goal-lens payload derived from state manager goal/arc
   state.
2. Feed this payload into:
   - semantic selector scoring,
   - sparse runtime synthesis prompts,
   - action grounding fact-pack prioritization,
   - beat generation and arc advancement telemetry.
3. Add lightweight goal progression heuristics (advance, stall, branch, setback)
   with explicit state transitions.
4. Expose lens/debug fields in existing debug endpoints without breaking current
   API contracts.

## Files Affected

- `src/services/state_manager.py`
- `src/services/semantic_selector.py`
- `src/services/storylet_selector.py`
- `src/services/world_memory.py`
- `src/api/game/story.py`
- `src/api/game/action.py`
- `tests/service/test_state_manager.py`
- `tests/service/test_semantic_selector.py`
- `tests/integration/test_narrative_eval_harness.py`

## Acceptance Criteria

- [ ] A canonical goal-lens payload is produced from state and persisted across
      session resume.
- [ ] Selector scoring and runtime synthesis include goal-lens context.
- [ ] Fact packs for freeform action grounding prioritize goal-relevant facts.
- [ ] Goal/arc transitions are observable through state/debug outputs.
- [ ] Narrative evaluation scenarios show reduced uncontrolled goal drift.
- [ ] Existing route payloads remain backward compatible.

## Risks & Rollback

Risk: over-weighting goal lens can reduce exploration diversity.

Rollback:

1. Add tunable weights and feature flags for goal-lens influence.
2. Revert to prior selector/context weighting if diversity/coherence regresses.
3. Keep arc metadata writes additive so rollback does not require destructive
   data migration.

