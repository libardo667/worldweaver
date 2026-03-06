# Add additive map-clarity and fallback-reason fields to turn responses

## Problem
When output quality drops, callers cannot quickly identify whether the turn came from projected pathing, degraded fallback, or sparse context. This slows debugging and reduces trust in sweep results.

## Proposed Solution
Expose lightweight diagnostics in `/api/next` and `/api/action` responses.

- Add additive fields such as `selection_mode`, `active_storylets_count`, `eligible_storylets_count`, `fallback_reason`, and `clarity_level`.
- Keep defaults empty or null-safe so existing clients are not broken.
- Ensure diagnostics are populated consistently in success and degraded paths.

## Files Affected
- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/services/turn_service.py`
- `src/models/schemas.py`
- `tests/api/test_game_endpoints.py`
- `tests/api/test_action_endpoint.py`

## Acceptance Criteria
- [ ] Turn responses include additive diagnostics for selection and fallback state.
- [ ] Diagnostic fields remain optional/backward compatible.
- [ ] Tests validate presence and shape in representative paths.
- [ ] No route or required payload contract breakage is introduced.
