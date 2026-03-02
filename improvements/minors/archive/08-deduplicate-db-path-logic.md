# Deduplicate database path resolution logic

## Problem

The database path selection logic (`DW_DB_PATH` env var → fallback to
`test_database.db` or `worldweaver.db`) appears in three places:

1. `src/database.py` lines 13-19 — the canonical version.
2. `src/services/story_smoother.py` lines 23-34 — a copy that reimplements
   the same logic to open its own SQLAlchemy engine.
3. `src/services/story_deepener.py` lines 21-33 — another copy.

The service copies can drift from the canonical version and they create
their own engines instead of reusing the shared one.

## Proposed Fix

Remove the duplicated path resolution from `story_smoother.py` and
`story_deepener.py`. Have both services accept a `Session` (or use the
shared `SessionLocal` from `src/database.py`) instead of constructing
their own engines. This aligns them with how every other service accesses
the database.

## Files Affected

- `src/services/story_smoother.py`
- `src/services/story_deepener.py`

## Acceptance Criteria

- [ ] `grep -rn "DW_DB_PATH" src/` returns only `src/database.py`
- [ ] Both services use the shared `SessionLocal` or an injected session
- [ ] Auto-improvement still runs correctly after storylet creation
