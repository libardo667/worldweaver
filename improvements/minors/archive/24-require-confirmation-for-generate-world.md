# Add confirmation guard to generate-world endpoint

## Problem

`POST /author/generate-world` in `src/api/author.py` lines ~489-493
deletes ALL existing storylets with `db.query(Storylet).delete()` before
generating new ones. There is no confirmation parameter, no dry-run
option, and no backup step. A single accidental call wipes the entire
content database irreversibly.

## Proposed Fix

Add a required `confirm_delete: bool = False` field to the
`WorldDescription` schema. If `confirm_delete` is not `True`, return a
422 response with a message explaining that existing storylets will be
deleted and asking the caller to set `confirm_delete: true`. This makes
destructive deletion opt-in rather than implicit.

## Files Affected

- `src/models/schemas.py` — add `confirm_delete` field to `WorldDescription`
- `src/api/author.py` — check `confirm_delete` before deleting

## Acceptance Criteria

- [ ] `POST /author/generate-world` without `confirm_delete: true` returns 422
- [ ] `POST /author/generate-world` with `confirm_delete: true` works as before
- [ ] The 422 response message clearly explains the consequence
