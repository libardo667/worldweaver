# Rename FastAPI app title to "WorldWeaver Backend"

## Problem

`main.py` currently labels the app title inconsistently (`"DwarfWeave Backend"`), which creates naming drift across docs and generated OpenAPI metadata.

## Proposed Solution

1. Update FastAPI app initialization title string to `"WorldWeaver Backend"`.
2. Verify OpenAPI docs still load and route behavior is unchanged.

## Scope Boundaries

- Limit behavior changes to FastAPI app metadata title only.
- Keep routes, payload schemas, and runtime behavior unchanged.
- Add/adjust tests only where title metadata is asserted.

## Assumptions

- OpenAPI `info.title` is sourced directly from `FastAPI(title=...)`.
- Renaming app title should not affect route registration or request handling.

## Files Affected

- `main.py`
- `tests/core/test_main.py` (if title assertion exists)

## Validation Commands

- `pytest -q`

## Acceptance Criteria

- [ ] FastAPI app title is `"WorldWeaver Backend"`.
- [ ] API behavior and paths remain unchanged.
- [ ] `pytest -q` passes.

## Rollback Plan

- Revert the commit(s) from branch `minor/49-rename-fastapi-title-worldweaver-backend`.
- No feature flags are needed for this metadata-only change.
- No migrations or state mutations are introduced.
