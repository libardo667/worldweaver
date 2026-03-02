# Narrative Beats as Semantic Field Lenses

## Problem

Currently, storylet selection is a simple proximity search between the player's context vector and storylet embeddings in `semantic_selector.py`. While this ensures *relevance*, it lacks *intentionality*. There is no concept of a "narrative beat" or "pacing" that can intentionally shift the probability field to create drama, tension, or thematic resonance (e.g., "warping the field toward community storylets after a successful help action" as mentioned in `VISION.md`).

## Proposed Solution

1.  **Introduce `NarrativeBeat` (or "Thematic Lens")**: A temporary semantic vector that is added to the base player context vector during selection.
2.  **Define Beats**: Create a set of "standard beats":
    - `IncreasingTension`: Pulled toward danger/conflict.
    - `ThematicResonance`: Pulled toward current world themes (cosmic, social, spec-specific).
    - `Catharsis`: Pulled toward resolution/social storylets.
3.  **Warping Mechanic**: Update `src/services/semantic_selector.py` to accept one or more active `beats`.
    - `final_vector = context_vector + sum(beat.vector * beat.intensity for beat in active_beats)`
4.  **Automatic Beat Triggering**: In `src/services/command_interpreter.py`, the LLM should optionally suggest a "following beat" (e.g., if the player burns a bridge, the interpreter suggests an `IncreasingTension` beat).
5.  **State Management**: Store active beats and their decay (e.g., 3 turns) in `AdvancedStateManager`.

## Files Affected

- `src/models/__init__.py`: Add `NarrativeBeat` or update `SessionVars`.
- `src/services/semantic_selector.py`: Update scoring to include beat-warping.
- `src/services/command_interpreter.py`: LLM suggests beats.
- `src/api/game.py`: Track/Pass beats in the game loop.

## Acceptance Criteria

- [x] Selection probability of "dark" storylets increases after "dark" actions even if the player's *static* state hasn't changed much.
- [x] Storylet selection can be intentionally steered for N turns by an active beat.
- [x] Multiple beats can be stacked/blended (weighted sum).
- [x] Beats have a "fade out" mechanism (intensity reduces each turn).

## Risks & Rollback

Incorrectly tuned beats could make selection feel random or "fixated" on one theme. Rollback by setting beat intensity/weights to zero in the selection logic.
