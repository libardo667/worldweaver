# Fix broken test imports and dead test files

## Problem

Several test files are broken and will fail on import:

1. `tests/api/test_author_race_condition.py` imports `author_commit` from
   `src.api.author`, but that function was removed (comment at author.py
   lines ~205-207). The test fails with `ImportError`.

2. `tests/api/test_author_duplicates.py` also imports `author_commit`.

3. `tests/contract/test_spatial_navigation.py` validates against uppercase
   direction strings (`"N"`, `"NE"`) but the API returns lowercase
   (`"north"`, `"northeast"`).

These dead tests create noise in the test suite and mask real failures.

## Proposed Fix

- Delete or archive `test_author_race_condition.py` and
  `test_author_duplicates.py` (the function they test no longer exists).
- Fix `test_spatial_navigation.py` to use lowercase direction strings
  matching the actual API output.

## Files Affected

- `tests/api/test_author_race_condition.py` — delete
- `tests/api/test_author_duplicates.py` — delete or fix
- `tests/contract/test_spatial_navigation.py` — fix direction strings

## Acceptance Criteria

- [ ] No test files fail on import
- [ ] `pytest tests/` has no `ImportError` failures from these files
- [ ] Spatial navigation test uses correct lowercase direction strings
