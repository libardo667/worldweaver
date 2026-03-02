# Add semantic selection debug score breakdown

## Problem

When storylet picks feel surprising, there is no straightforward way to inspect semantic score components (similarity, weight, recency penalty, floor clamp).

## Proposed Solution

1. Add optional debug output mode in `semantic_selector.py` returning score components per candidate.
2. Expose a debug endpoint or query flag in `/api/next` for local development.
3. Log top candidates with component scores at debug level.

## Files Affected

- `src/services/semantic_selector.py`
- `src/api/game.py`
- `tests/service/test_semantic_selector.py`

## Acceptance Criteria

- [ ] Developers can inspect per-storylet scoring components for a turn.
- [ ] Debug mode does not alter production selection behavior.
- [ ] Tests cover expected score decomposition values.
