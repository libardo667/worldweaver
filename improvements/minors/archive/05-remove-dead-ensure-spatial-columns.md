# Remove dead _ensure_spatial_columns method

## Problem

`src/services/spatial_navigator.py` lines 193-196 define
`_ensure_spatial_columns()` as a no-op method (empty body or pass). It is
called during initialisation but does nothing. The spatial data is stored
in the `position` JSON column, not in separate `spatial_x` / `spatial_y`
columns, making this method obsolete. Its presence is misleading — it
suggests a migration step that never happens.

Similarly, `auto_assign_coordinates()` (line 379) writes to `spatial_x`
and `spatial_y` columns that do not exist in the model definition
(`src/models/__init__.py`), meaning those writes silently fail or error
depending on the SQLite schema state.

## Proposed Fix

1. Delete `_ensure_spatial_columns()` and its call site.
2. Change `auto_assign_coordinates()` to update the `position` JSON column
   (which is the actual schema) instead of non-existent `spatial_x/y`
   columns.

## Files Affected

- `src/services/spatial_navigator.py`

## Acceptance Criteria

- [ ] `_ensure_spatial_columns` method no longer exists
- [ ] `auto_assign_coordinates` writes to `position` JSON, not `spatial_x`/`spatial_y`
- [ ] Existing spatial tests still pass
