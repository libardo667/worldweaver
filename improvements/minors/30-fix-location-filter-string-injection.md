# Fix location filter string interpolation in game.py

## Problem

`src/api/game.py` lines ~333-336 and ~429-432 filter storylets by
location using raw string interpolation into a SQLAlchemy `contains()`:

```python
Storylet.requires.contains(f'"location": "{current_location}"')
```

This is fragile in two ways:
1. It breaks if the JSON is formatted with different whitespace (e.g.,
   `"location":"forest"` without a space after the colon).
2. `current_location` is interpolated directly into the filter string
   with no escaping, which could allow injection of unexpected patterns.

## Proposed Fix

Instead of string-matching on the raw JSON column, load the `requires`
dict from each storylet and filter in Python, or use SQLAlchemy's JSON
path extraction if supported. The simplest correct fix is to query all
storylets and filter `json.loads(s.requires).get("location") == current_location`
in Python — the storylet count is small enough that this is not a
performance concern.

## Files Affected

- `src/api/game.py`

## Acceptance Criteria

- [ ] Location filtering works regardless of JSON whitespace formatting
- [ ] No raw string interpolation of user input into query filters
- [ ] Existing spatial navigation tests still pass
