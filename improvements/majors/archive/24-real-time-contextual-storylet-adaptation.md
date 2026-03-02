# Real-Time Contextual Storylet Adaptation

## Problem

Storylets currently have `text_template` which uses simple `{variable}` substitution. This is "Mad Libs" style generation. For a truly living world, storylets should incorporate the *flavor* of the current situation—mentioning recent world events, specific NPC names from history, or the player's current emotional state—without requiring the author to anticipate every possible variable.

## Proposed Solution

1.  **Late-Bound Narrative Expansion**: After a storylet is "picked" but before it is returned to the client, pass the `text_template` and the full `AdvancedStateManager` context to the LLM.
2.  **Context-Aware Rewriting**: Instruct the LLM to "Expand this storylet to reflect the current world state while keeping the core choices intact."
3.  **Local History Injection**: Explicitly inject the last 2-3 `WorldEvent` summaries into the prompt to provide "connective tissue" between scenes.
4.  **Choice Adaptive Labels**: Rewrite choice labels if they logically change based on context (e.g., "Attack the merchant" becomes "Attack the merchant you just cheated").

## Files Affected

- `src/services/llm_service.py`: New function `adapt_storylet_to_context(storylet, context)`.
- `src/api/game.py`: Call adaptation service before responding to `/next`.
- `src/config.py`: Add `ENABLE_RUNTIME_ADAPTATION` flag.

## Acceptance Criteria

- [x] Storylet text mentions something that happened in a *previous* freeform action.
- [x] Descriptions of the environment change based on the current weather/danger level in `state_manager.environment`.
- [x] No manual variable substitution `{...}` required in the core template if the LLM can infer it from context.

## Risks & Rollback

Runtime LLM calls for every "Next" action will increase latency and cost. Rollback by disabling the `ENABLE_RUNTIME_ADAPTATION` flag and falling back to standard `SafeDict` template rendering.
