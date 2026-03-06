# Orchestration Duplication And Fallback Map (Wave 2)

Status: `evidence_only`  
Scope: identify overlap and fallback chains without refactoring

## Duplicate Endpoint-Layer Patterns

### Trace id resolution helpers
- `src/api/game/story.py:29`
- `src/api/game/action.py:83`
- `src/api/game/turn.py:36`

Pattern: each module defines near-equivalent `_active_trace_id` logic.

### Session lock and orchestrator delegation
- `src/api/game/story.py:44`
- `src/api/game/action.py:104`
- `src/api/game/turn.py:60`

Pattern: each endpoint enters `session_mutation_lock` and delegates to `TurnOrchestrator`.

### Prefetch scheduling blocks
- `src/api/game/story.py:92`
- `src/api/game/action.py:141`
- `src/api/game/action.py:219`
- `src/api/game/turn.py:85`
- `src/api/game/turn.py:121`

Pattern: repeated schedule + best-effort exception wrapper + timing capture.

### Request timing log envelopes
- `src/api/game/story.py:113`
- `src/api/game/action.py:158`
- `src/api/game/action.py:238`
- `src/api/game/turn.py:144`

Pattern: repeated request completion payload + route timing update/reset.

### Semantic goal parsing duplication
- `src/api/game/action.py:33`
- `src/services/turn_service.py:52`

Pattern: duplicated `_SEMANTIC_GOAL_PATTERN` and extraction utility.

## Fallback Chains In Canonical Turn Orchestrator

### Action pipeline fallback chain
- `src/services/turn_service.py:431` (`enable_strict_three_layer_architecture`)
- `src/services/turn_service.py:435` (`enable_staged_action_pipeline`)
- `src/services/turn_service.py:437` / `:490` (`interpret_action_intent`)
- `src/services/turn_service.py:474` / `:524` (`interpret_action` deterministic fallback)

Observed chain:
1. try staged intent path
2. validate intent
3. fall back to deterministic interpreter when staged intent unavailable
4. strict mode can return deterministic acknowledgement payload

### Next-turn fallback chain
- `src/services/turn_service.py:955` (JIT beat generation failure fallback)
- `src/services/turn_service.py:991` (`no_eligible_storylets` fallback reason)
- `src/services/turn_service.py:1092` / `:1093` (`template_fallback_after_adaptation`)

Observed chain:
1. JIT beat path when enabled
2. on JIT failure, return to storylet selection path
3. if no storylet selected, emit engine-idle fallback text
4. if adaptation yields empty text, fall back to template render

## Pruning Implication (No Action Yet)
- Highest merge/simplify leverage is endpoint wrapper duplication, not reducer/state mutation core.
- Fallback ladders are correctness-critical and should be simplified only with strong regression coverage.
