# Add created_at and updated_at timestamps to Storylet model

## Problem

`SessionVars` has an `updated_at` column, but `Storylet` has no timestamp
columns at all. This means you cannot determine when a storylet was
created, sort by creation order, query "recently generated" storylets, or
implement time-based recency penalties for the semantic selection engine.

## Proposed Fix

Add `created_at` and `updated_at` columns to the `Storylet` model in
`src/models/__init__.py`, matching the pattern used by `SessionVars`:

```python
created_at = Column(DateTime, server_default=func.now())
updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

Since there is no migration system yet (improvement 20), this will only
take effect on fresh databases until Alembic is added.

## Files Affected

- `src/models/__init__.py`

## Acceptance Criteria

- [ ] `Storylet` has `created_at` and `updated_at` columns
- [ ] New storylets get automatic timestamps
- [ ] Updated storylets get a refreshed `updated_at`
