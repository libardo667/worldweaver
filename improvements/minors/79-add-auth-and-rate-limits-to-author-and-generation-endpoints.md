# Add auth and rate limits to author and generation endpoints

## Problem

Author endpoints expose powerful write/generation operations (`/author/*`) with
no access control or request throttling in the current default path. This is
high risk if the service is exposed beyond localhost.

## Proposed Solution

Add minimal protection layers:

1. Add optional API key (or equivalent simple auth) guard for `/author/*`.
2. Add configurable rate limiting for expensive generation/analyzer routes.
3. Keep local dev ergonomics by allowing explicit opt-out in development.
4. Add route tests for unauthorized and rate-limited responses.

## Files Affected

- `main.py`
- `src/api/author/__init__.py`
- `src/api/author/world.py`
- `src/api/author/generate.py`
- `src/api/author/populate.py`
- `src/config.py`
- `tests/api/test_author_auth.py` (new)

## Acceptance Criteria

- [ ] When auth is enabled, unauthorized `/author/*` requests are rejected.
- [ ] Expensive generation endpoints return `429` when exceeding configured
      limits.
- [ ] Auth/rate-limit settings are environment-configurable and documented.
- [ ] Existing authorized author flows continue to function.

