# Add LLM preflight healthchecks

## Problem
The backend engine eagerly initializes game sessions and queues up complex generation pipelines without first verifying if the LLM provider is correctly configured, reachable, or authenticated. If an API key is missing, malformed, or the configured model is geographically restricted, the engine only discovers this *during* the generation phase, collapsing the entire chain into fallback text.

## Proposed Solution
Deploy a diagnostic "preflight" check to validate the LLM integration layer before it is heavily relied upon:
1. **Startup Check:** During `uvicorn` startup (in `lifespan` or a dedicated init script), ping the `get_llm_client()` with a tiny, low-token healthcheck request (e.g., "return the word OK") to verify the configuration actually works.
2. **Graceful Degradation Toggle:** If the preflight fails (timeout, auth error, model not found), automatically flip the internal `is_ai_disabled()` state and clearly warn the server operator that the game is running in Deterministic Fallback Mode.
3. **Diagnostic Endpoint:** Expose a dedicated `/api/dev/health/llm` endpoint that returns detailed reachability metrics, current model resolution, and environment variables for easier debugging.

## Files Affected
- `main.py` (Add preflight hook to app `lifespan`)
- `src/services/llm_client.py` (Implement `verify_connection()` helper)
- `src/config.py` (Manage a runtime `ai_available` flag)
- `src/api/game/state.py` (Add the diagnostic endpoint)

## Acceptance Criteria
- [ ] Booting the server with an invalid `.env` model string or API key logs an immediate, clear `WARNING` during startup.
- [ ] A failed preflight allows the server to start, but cleanly defaults the engine to deterministic mode without needing to wait for actual game requests to fail.
- [ ] Hitting the `/api/dev/health/llm` endpoint returns the active LLM provider status.

## Risks & Rollback
**Risk:** Startup preflight calls consume API credits (even fractions of a cent) every time the server restarts with `--reload`.
**Mitigation:** Cache the preflight success state locally or make it incredibly lightweight. We can also disable it in rapid-dev modes if it becomes bothersome.
**Rollback:** Remove the lifespan hook and diagnostic endpoint.
