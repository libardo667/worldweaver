# Move hardcoded default variables out of get_state_manager

## Problem

`src/api/game.py` `get_state_manager()` (lines 43-51) sets hardcoded
defaults on every session load:

```python
manager.variables.setdefault("name", "Adventurer")
manager.variables.setdefault("danger", 0)
manager.variables.setdefault("has_pickaxe", True)
```

These values are game-design decisions buried in API plumbing code. They
are applied on every call — including when loading a session that
intentionally set `has_pickaxe` to `False` — because `setdefault` only
fires when the key is absent, but the broader pattern of mixing API code
with game defaults is fragile and hard to discover.

## Proposed Fix

Move the default variable dict to a constant in `src/services/seed_data.py`
(or a new `src/defaults.py`) as `DEFAULT_SESSION_VARS`. Reference it from
`get_state_manager` with a single `for k, v in DEFAULT_SESSION_VARS.items():
manager.variables.setdefault(k, v)` loop. This makes game defaults
discoverable and editable in one place.

## Files Affected

- `src/api/game.py` — remove inline defaults, import constant
- `src/services/seed_data.py` (or `src/defaults.py`) — define constant

## Acceptance Criteria

- [ ] No hardcoded variable defaults remain in `game.py`
- [ ] Defaults are defined in a single, clearly named location
- [ ] Existing sessions continue to load correctly
