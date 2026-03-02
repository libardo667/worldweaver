# Split the game API router into topic subrouters while preserving all public paths

## Problem

`src/api/game.py` is a large, multi-responsibility module (story progression, state endpoints, spatial endpoints, world memory endpoints, action endpoint). This increases maintenance cost and slows safe iteration.

## Proposed Solution

1. Create package structure:
   - `src/api/game/__init__.py`
   - `src/api/game/story.py`
   - `src/api/game/state.py`
   - `src/api/game/spatial.py`
   - `src/api/game/world.py`
   - `src/api/game/action.py`
2. Move endpoint groups into topic modules with local `APIRouter()` instances.
3. In `src/api/game/__init__.py`, include subrouters into one exported `router` object.
4. Keep external route paths unchanged under existing `/api` prefix.
5. Keep shared helpers/service imports centralized to avoid duplication.

## Files Affected

- `src/api/game.py` (replaced by package layout)
- `src/api/game/__init__.py` (new)
- `src/api/game/story.py` (new)
- `src/api/game/state.py` (new)
- `src/api/game/spatial.py` (new)
- `src/api/game/world.py` (new)
- `src/api/game/action.py` (new)
- `main.py`
- `tests/api/test_game_endpoints.py`
- `tests/api/test_action_endpoint.py`
- `tests/api/test_world_endpoints.py`
- `tests/contract/test_spatial_*.py`

## Acceptance Criteria

- [ ] All existing game endpoints remain reachable at identical URLs.
- [ ] Route response shapes remain unchanged.
- [ ] `main.py` still mounts `game.router` at `/api`.
- [ ] Router files are topic-focused and smaller.
- [ ] `pytest -q` passes.

## Risks & Rollback

Risk is route registration mistakes during file moves. Roll back by restoring monolithic `src/api/game.py` and re-pointing imports in `main.py`.
