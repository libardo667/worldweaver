# Batch commit in spatial_navigator._place_storylet

## Problem

`src/services/spatial_navigator.py` `_place_storylet` calls `db.commit()`
inside the loop for every single storylet placement. If 20 storylets are
being positioned, that is 20 separate commits — far slower than a single
batch commit and increases the window for partial-write failures.

## Proposed Fix

Move `db.commit()` out of the loop so it runs once after all placements
are complete. Wrap the loop in a try/except that calls `db.rollback()` on
failure so partial writes don't persist.

## Files Affected

- `src/services/spatial_navigator.py`

## Acceptance Criteria

- [ ] Only one `db.commit()` call for the entire batch of placements
- [ ] A failure mid-batch rolls back all placements, not just the failing one
- [ ] Existing tests still pass
