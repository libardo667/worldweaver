# Add idempotency keys for freeform action event recording

## Problem

Retries or duplicate client submits can record the same action event multiple times, skewing world history and semantic context.

## Proposed Solution

1. Add optional `idempotency_key` to `ActionRequest`.
2. Store recent keys per session and skip duplicate event inserts.
3. Return a deterministic response for duplicate submissions.

## Files Affected

- `src/models/schemas.py`
- `src/api/game.py`
- `src/services/world_memory.py`
- `tests/api/test_action_endpoint.py`

## Acceptance Criteria

- [x] Duplicate action submissions with the same key do not create duplicate `WorldEvent` rows.
- [x] First and duplicate responses are consistent for the same request body.
- [x] Existing clients without idempotency keys continue to work.
