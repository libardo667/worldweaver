# Add deterministic fixtures for semantic selector regression tests

## Problem

Current semantic selection tests can miss subtle regressions because candidate sets and random selection are not consistently replayable across runs.

## Proposed Solution

1. Add fixed embedding fixtures and deterministic random seeds for selector tests.
2. Test score ordering and weighted pick behavior with stable expectations.
3. Add edge-case fixtures for zero vectors and recency penalties.

## Files Affected

- `tests/service/test_semantic_selector.py`
- `src/services/semantic_selector.py` (if deterministic helper is needed)

## Acceptance Criteria

- [ ] Selector test outcomes are stable across repeated local/CI runs.
- [ ] Tests cover score floor and recency penalty behavior explicitly.
- [ ] Failures clearly indicate ranking or weighting regressions.
