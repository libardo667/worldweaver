# Rename FastAPI app title to "WorldWeaver Backend"

## Problem

`main.py` currently labels the app title inconsistently (`"DwarfWeave Backend"`), which creates naming drift across docs and generated OpenAPI metadata.

## Proposed Solution

1. Update FastAPI app initialization title string to `"WorldWeaver Backend"`.
2. Verify OpenAPI docs still load and route behavior is unchanged.

## Files Affected

- `main.py`
- `tests/core/test_main.py` (if title assertion exists)

## Acceptance Criteria

- [ ] FastAPI app title is `"WorldWeaver Backend"`.
- [ ] API behavior and paths remain unchanged.
- [ ] `pytest -q` passes.
