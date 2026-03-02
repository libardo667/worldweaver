# Add OpenAPI examples for core game endpoint payloads

## Problem

Core endpoints (`/api/next`, `/api/action`, spatial endpoints) have limited request/response examples, which slows frontend and tooling integration.

## Proposed Solution

1. Add `json_schema_extra` examples to key Pydantic models in `src/models/schemas.py`.
2. Include at least one realistic example for each core endpoint model.
3. Verify generated docs display example payloads correctly.

## Files Affected

- `src/models/schemas.py`
- `tests/contract/test_error_envelopes.py` (or dedicated schema test)

## Acceptance Criteria

- [ ] OpenAPI docs show concrete request and response examples for core game endpoints.
- [ ] Examples validate against the actual model schemas.
- [ ] Contract consumers can copy examples directly for smoke tests.
