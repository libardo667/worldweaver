# Add session_id format validation to game endpoints

## Problem

Game endpoints accept any string as a `session_id` with no validation.
A request with `session_id=""` or `session_id="../../etc/passwd"` is
happily processed — the empty string becomes a database primary key, and
path-like strings are stored in the JSON column. While SQLite prevents
actual path traversal, there is no length limit or format constraint, so
garbage sessions accumulate and the cleanup logic has to process them.

## Proposed Fix

Add a Pydantic validator (or a FastAPI `Depends` guard) that enforces:
- Length between 1 and 128 characters.
- Matches `^[a-zA-Z0-9_-]+$` (alphanumeric, hyphens, underscores).
- Returns 422 with a clear message on violation.

Apply this to every endpoint that takes `session_id` as a path or body
parameter.

## Files Affected

- `src/models/schemas.py` — add validated `SessionId` type
- `src/api/game.py` — use the validated type in endpoint signatures

## Acceptance Criteria

- [ ] `session_id=""` returns 422
- [ ] `session_id="a" * 200` returns 422
- [ ] `session_id="valid-session_123"` is accepted
