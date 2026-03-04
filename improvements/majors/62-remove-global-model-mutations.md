# Remove unsafe global model mutations from runtime

## Problem
The `/api/settings/model` endpoint (implemented in `settings_api.py`) globally mutates the `src.config.settings.llm_model` singleton via `settings.llm_model = new_model_id`. This is extremely dangerous in an async, heavily-threaded environment like `uvicorn`: it overrides the loaded `.env` configuration for the entire lifetime of the process across all users and sessions. If a dev server process is orphaned, this stale runtime mutation persists, silently hijacking all future generation requests.

## Proposed Solution
Refactor the model selection architecture to prevent mutating process globals:
1. **Session-Scoped Preference:** Store preferred models per-session in the database or cache, rather than in the global pydantic-settings singleton.
2. **Context-Aware Client Factory:** Update `get_model()` and `get_llm_client()` to accept an optional `session_id` or `user_id` to resolve the currently active model, falling back to the immutable `settings.llm_model` defined in `.env`.
3. **Endpoint Refactor:** Modify `switch_model` to persist the setting securely against the active session state instead of modifying the config singleton.

## Files Affected
- `src/config.py` (Freeze the settings singleton fields if possible, or heavily document immutability)
- `src/api/game/settings_api.py` (Remove global assignment, write to session/DB)
- `src/services/llm_client.py` (Update `get_model` resolution logic)
- `src/services/state_manager.py` (Potentially route model preference schema through here)

## Acceptance Criteria
- [ ] Calling `PUT /api/settings/model` does not alter `src.config.settings.llm_model`.
- [ ] Subsequent LLM calls correctly honor the dynamically selected model for that specific requester.
- [ ] A fresh session (or different user) continues to default to the `.env` model unless explicitly overridden.

## Risks & Rollback
**Risk:** Plombing a `session_id` context down to the shared `llm_client.py` factory may require updating several disparate method signatures across the codebase.
**Mitigation:** We can utilize `ContextVar` (similar to the existing `trace_id` implementation) to implicitly pass the current request's model preference without breaking thousands of function signatures.
**Rollback:** Revert to the mutating singleton pattern.
