# Unify error response format across all endpoints

## Problem

Error handling is inconsistent across the API surface:

- `src/api/game.py` raises `HTTPException` on errors (correct).
- `src/api/author.py` returns plain `{"error": "..."}` dicts with a 200
  status code in `generate_intelligent_storylets` (line 315),
  `generate_targeted_storylets` (line 356), `get_storylet_analysis`
  (line 407), and `generate_world_from_description` (line 466).

A frontend cannot rely on HTTP status codes to detect failures because some
failures return 200. This makes the API unusable for any real client
integration.

## Proposed Solution

1. Define a standard error envelope in `src/models/schemas.py`:
   ```python
   class ErrorResponse(BaseModel):
       error: str
       detail: Optional[str] = None
   ```
2. Replace every `return {"error": ...}` in `author.py` with a proper
   `raise HTTPException(status_code=..., detail=...)`.
3. Add a FastAPI exception handler in `main.py` that catches unhandled
   exceptions and returns the envelope with a 500 status code, without
   leaking stack traces.
4. Add a contract test that asserts every error response has the correct
   status code and envelope shape.

## Files Affected

- `src/api/author.py` — replace dict returns with HTTPException raises
- `src/models/schemas.py` — add `ErrorResponse` model
- `main.py` — add global exception handler
- `tests/contract/test_error_envelopes.py` (new)

## Acceptance Criteria

- [ ] No endpoint returns a 200 status code on failure
- [ ] All error responses have `{"detail": "..."}` body (FastAPI default)
- [ ] Unhandled exceptions return 500 with a safe message (no traceback)
- [ ] Contract test verifies error shape for at least 5 error scenarios

## Risks & Rollback

Any existing frontend code that checks for `{"error": ...}` in 200
responses will need updating. Rollback: revert `author.py` changes.
