# Prefer cached frontier stubs for next-scene selection when available

## Problem
Prefetch only improves perceived latency if the system actually uses prefetched candidates for the next scene. Otherwise the player still waits for generation/scoring.

## Proposed Solution
Update selection flow to:
- check the prefetch cache first for eligible stubs matching current location and requirements,
- select from cached stubs with existing semantic/recency heuristics,
- fall back to the existing storylet selector if cache is empty or stale.

This should be additive and conservative.

## Files Affected
- `src/services/storylet_selector.py`
- `src/services/prefetch_service.py`
- `tests/service/test_storylet_selector.py` (new cases for cache-preference)

## Acceptance Criteria
- [x] When cache contains eligible stubs, selection prefers them.
- [x] When cache is empty/stale, behavior matches current selection.
- [x] No API payload changes.
- [x] `pytest -q` passes.
