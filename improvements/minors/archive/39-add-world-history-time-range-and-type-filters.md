# Add time range and event type filters to world history endpoint

## Problem

`GET /api/world/history` currently supports only session and limit filters, making it difficult to inspect specific windows (for example, "last hour") or only permanent changes.

## Proposed Solution

1. Add optional query parameters: `event_type`, `since`, and `until`.
2. Apply validated filters in world history query logic.
3. Add response metadata echoing active filters for debugging.

## Files Affected

- `src/api/game.py`
- `src/services/world_memory.py`
- `src/models/schemas.py`
- `tests/api/test_world_endpoints.py`

## Acceptance Criteria

- [x] History endpoint filters by event type and time range when provided.
- [x] Invalid timestamps return a clear 422 validation error.
- [x] Existing unfiltered requests behave exactly as before.
