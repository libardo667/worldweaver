# Add preflight checks and a clear dev command surface

## Problem
Even with existing documentation, developers still have to infer runtime prerequisites (env vars, ports, dependency state) before running backend/client together. Missing or inconsistent setup causes avoidable startup failures and slows iteration.

## Proposed Solution
Introduce a low-risk preflight and command-surface improvement that validates local readiness before startup.

1. Add a lightweight preflight command that checks:
   - required runtime tools (`python`, `node`, `npm`, optional `docker`)
   - expected env file presence (`.env`, `client/.env.local`)
   - essential API key/env settings (with non-secret pass/fail messaging)
2. Add concise command aliases/wrappers for common local tasks:
   - start backend
   - start client
   - run tests/build checks
3. Update docs to make preflight + run sequence explicit and copy/paste-friendly.

## Files Affected
- `scripts/*` (new preflight and wrapper commands)
- `client/README.md`
- `README.md` (if present) or equivalent top-level runtime doc
- `.env.example` (clarifications only)

## Acceptance Criteria
- [x] Running preflight produces clear pass/fail output with actionable remediation steps.
- [x] Common local commands are documented in one place and match actual scripts.
- [x] Startup failures from missing required setup are reduced to explicit preflight failures.
- [x] Existing runtime behavior and API contracts remain unchanged.
