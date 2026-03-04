# Differentiate LLM pipeline error handling and telemetery

## Problem
Currently, the LLM generation pipeline (e.g., `generate_world_bible`, `generate_next_beat`) wraps its core logic in a broad `try...except Exception:` block. When *any* error occurs—whether it's a transient network timeout, an authentication failure, or a critical Pydantic `ValidationError`—the system silently swallows the exception and returns deterministic fallback text. This makes the system appear "successful" to the frontend while completely masking catastrophic integration bugs.

## Proposed Solution
Implement defensive, differentiated exception handling at the boundary between the game engine and the stochastic LLM provider:
1. **Specific Catch Blocks:** Separate exceptions by severity. `TimeoutError`s, `AuthenticationError`s, and `ValidationError`s should be caught and logged explicitly (`logger.error` or `logger.critical`) with full stack traces before invoking the fallback mechanism.
2. **Semantic Misses vs Engine Failures:** If the LLM returns garbled JSON, that is a "semantic miss" (warn and fallback). If the API wrapper throws a Pydantic schema validation error *before* the network request is even sent, that is an "engine failure" (error and alert).
3. **Client Visibility:** Optionally, append a lightweight diagnostic flag to the API response (e.g., `_fallback_reason: "timeout"`) so frontend developers can see why dynamic generation was bypassed.

## Files Affected
- `src/services/llm_service.py` (Refactor `try...except` blocks in all generation functions)
- `src/services/llm_client.py` (Ensure instrumented proxies raise identifiable exception types)

## Acceptance Criteria
- [ ] Simulating an LLM timeout triggers an explicit `logger.error` indicating a timeout occurred, preceding the fallback text.
- [ ] Triggering a schema `ValidationError` (e.g., passing invalid arguments to the generator) emits a critical traceback to the server console.
- [ ] The fallback text mechanism still reliably functions as the ultimate safety net for unrecoverable errors.

## Risks & Rollback
**Risk:** Exposing error descriptors in the API payload could leak internal infrastructure details.
**Mitigation:** The `_fallback_reason` flag should be strictly categorized (e.g., "timeout", "schema_error", "rate_limit") rather than dumping raw stack traces.
**Rollback:** Revert the exception handling back to a monolithic `except Exception:` block.
