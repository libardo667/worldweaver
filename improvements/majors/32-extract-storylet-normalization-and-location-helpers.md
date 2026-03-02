# Extract storylet normalization and location lookup helpers from the game API

## Problem

`src/api/game.py` currently owns internal helper logic for:
- normalizing `requires` payloads,
- normalizing choices,
- finding storylets by location.

This duplicates behavior concerns inside the router layer and makes reuse difficult across services and future subrouters.

## Proposed Solution

1. Create a new service helper module (for example `src/services/storylet_utils.py`) containing:
   - `normalize_requires(value) -> dict`
   - `normalize_choice(choice_dict) -> {"label": str, "set": dict}`
   - `storylet_location(storylet) -> Optional[str>`
   - `find_storylet_by_location(db, location) -> Optional[Storylet]`
2. Move existing helper behavior from `src/api/game.py` to that service module without changing semantics.
3. Replace local/private helper usage in `src/api/game.py` with imported service helpers.
4. Add targeted service tests for legacy JSON-string `requires`, `None`, and malformed input.

## Files Affected

- `src/services/storylet_utils.py` (new)
- `src/api/game.py`
- `tests/service/test_storylet_utils.py` (new)
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [ ] No API route signatures or payload shapes change.
- [ ] All previous helper behaviors in `src/api/game.py` are preserved.
- [ ] Legacy `requires` forms (dict, JSON string, `None`) normalize identically.
- [ ] `pytest -q` passes.

## Risks & Rollback

Risk is subtle normalization regressions affecting selection and spatial location resolution. Roll back by restoring original helper implementations in `src/api/game.py` and removing the new service module.
