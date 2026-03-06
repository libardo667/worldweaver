# Add .env example and a clear golden-path verify command for onboarding

## Problem

Preflight tooling expects `.env`, but onboarding still depends on ad hoc variable
discovery. New contributors lack a single, explicit copy-and-run startup path.

## Proposed Solution

Provide an explicit onboarding baseline:

1. Add `.env.example` with all required and optional environment variables plus
   safe placeholder values/comments.
2. Add/align docs to highlight one golden-path verification command:
   `python scripts/dev.py verify`.
3. Ensure preflight messaging points directly to `.env.example`.

## Files Affected

- `.env.example` (new)
- `README.md`
- `scripts/dev.py`

## Acceptance Criteria

- [ ] `.env.example` exists with required variables documented.
- [ ] README includes a minimal onboarding path ending in
      `python scripts/dev.py verify`.
- [ ] `scripts/dev.py preflight` messaging references `.env.example`.
- [ ] A fresh clone can follow documented steps to reach a passing verify run
      (assuming valid API keys are supplied).

