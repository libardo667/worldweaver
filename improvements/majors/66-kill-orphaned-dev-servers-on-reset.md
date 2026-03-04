# Automatically terminate orphaned uvicorn processes on dev reset

## Problem
During active development, restarting the `uvicorn` development server or reloading the frontend UI can occasionally leave orphaned Windows `python.exe` processes running in the background. Because these zombie processes still listen on the host (`localhost:8000`), they intercept API traffic destined for the *new* server instance. Crucially, these orphans trap stale runtime state (like overridden LLM models) and outdated `.env` settings, leading to "ghost" bugs that are impossible to diagnose by looking at the current codebase.

## Proposed Solution
Enhance the development reset endpoints and server startup sequencing to actively hunt and terminate orphaned worker processes:
1. **Startup Port Sweeping:** Before `uvicorn` attempts to bind to the primary API port, implement a lightweight preflight script (e.g., in a `dev_start.py` wrapper) that detects any existing process holding the target port and gracefully (or forcefully) kills it.
2. **Dev Hard Reset Extension:** Optionally augment the `POST /api/dev/hard-reset` endpoint to signal a worker shutdown cascade, ensuring that when a developer requests a total world wipe, any lingering threadpools or background tasks are also purged.
3. **Cross-Platform Compatibility:** Ensure the process termination logic abstracts underlying OS commands (e.g., using `psutil` rather than raw Windows `taskkill` or Linux `kill -9`), or isolate the utility strictly for local dev workflows via an npm script hook.

## Files Affected
- `package.json` (Add a `predev` or `clean:port` helper script)
- `src/api/game/state.py` (Enhance `/dev/hard-reset` telemetry)
- `scripts/dev_start.py` or similar runner (Implement port sweep logic)

## Acceptance Criteria
- [ ] Running the dev startup command automatically terminates any pre-existing server process bound to the primary API port.
- [ ] The `dev/hard-reset` action cleanly flushes all runtime state, ensuring no background AI generation threads from a previous run survive.
- [ ] Operating system commands used for cleanup are platform-agnostic (or clearly documented if Windows-only).

## Risks & Rollback
**Risk:** Force-killing processes holding port 8000 might accidentally terminate an unrelated service or a critical background job completely unrelated to WorldWeaver.
**Mitigation:** The cleanup logic must verify that the process holding the port is actually a Python process running the `WorldWeaver` entrypoint before issuing the kill signal. 
**Rollback:** Revert the startup wrapper and remove the automated `taskkill` hooks, leaving port management to the developer.
