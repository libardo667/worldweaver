# Add Pydantic response models for spatial endpoints

## Problem

`GET /api/spatial/navigation`, `POST /api/spatial/move`,
`GET /api/spatial/map`, and `POST /api/spatial/assign-positions` in
`src/api/game.py` all return plain `dict` with no Pydantic response model.
This means no automatic OpenAPI documentation for response shapes, no
response validation, and no type safety for frontend consumers.

## Proposed Fix

Add response models to `src/models/schemas.py`:
- `SpatialNavigationResponse` — available directions, current position,
  location storylets
- `SpatialMoveResponse` — new position, storylet at new location
- `SpatialMapResponse` — grid of positions and their storylets
- `SpatialAssignResponse` — count of storylets assigned

Apply these as `response_model=` on each endpoint.

## Files Affected

- `src/models/schemas.py` — new response models
- `src/api/game.py` — add `response_model=` to 4 endpoints

## Acceptance Criteria

- [ ] All 4 spatial endpoints have Pydantic response models
- [ ] OpenAPI docs (`/docs`) show the response schemas
- [ ] Existing tests still pass (response shape hasn't changed, just documented)
