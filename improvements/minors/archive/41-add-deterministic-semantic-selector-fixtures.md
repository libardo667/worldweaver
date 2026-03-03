# Add deterministic fixtures and score breakdown tooling for semantic selector regression tests

## Problem

Current semantic selection tests can miss subtle regressions because candidate sets and random selection are not consistently replayable across runs. When picks feel surprising, there is also limited introspection into score components (similarity, floor clamp, recency penalty, weight).

## Proposed Solution

1. Add fixed embedding fixtures and deterministic random seeds for selector tests.
2. Test score ordering and weighted pick behavior with stable expectations.
3. Add edge-case fixtures for zero vectors and recency penalties.
4. Add optional debug score breakdown output in `semantic_selector.py`.
5. Expose breakdown through a debug query flag or dev-only endpoint path for `/api/next`.

## Files Affected

- `tests/service/test_semantic_selector.py`
- `src/services/semantic_selector.py`
- `src/api/game.py`

## Acceptance Criteria

- [x] Selector test outcomes are stable across repeated local/CI runs.
- [x] Tests cover score floor and recency penalty behavior explicitly.
- [x] Developers can inspect per-candidate scoring components in debug mode.
- [x] Debug output does not alter production selection behavior.
- [x] Failures clearly indicate ranking or weighting regressions.
