# Fix invalid CORS configuration

## Problem

`main.py` sets `allow_origins=["*"]` with `allow_credentials=True`. Per
the CORS specification, `Access-Control-Allow-Origin: *` is not compatible
with `Access-Control-Allow-Credentials: true` — browsers will reject the
response. FastAPI/Starlette may silently handle this, but the configuration
is semantically wrong.

## Proposed Fix

Either:
- Remove `allow_credentials=True` (simplest, appropriate for a local dev tool), or
- Replace `allow_origins=["*"]` with explicit origins (e.g.,
  `["http://localhost:3000", "http://localhost:8080"]`) if credentials
  are actually needed.

The first option is recommended since the project currently has no
authentication and credentials are not used.

## Files Affected

- `main.py`

## Acceptance Criteria

- [ ] CORS configuration is spec-compliant
- [ ] Cross-origin requests from the frontend still work
