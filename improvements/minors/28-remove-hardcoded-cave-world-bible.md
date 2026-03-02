# Remove hardcoded cave/mine world bible from auto_populate

## Problem

`src/services/game_logic.py` `auto_populate_storylets` (lines ~171-215)
hardcodes a mine/cave-themed world bible with themes like `cave_system`,
`mineshaft`, `ore`, and `has_pickaxe`. If a user generates a pirate world,
a sci-fi world, or anything non-mining, this function pollutes it with
Dwarf Fortress content. The function also does not accept a `world_bible`
parameter, so there is no way to contextualize it.

## Proposed Fix

Make `auto_populate_storylets` accept an optional `world_bible` parameter.
If provided, use it. If not, use a generic/neutral bible that doesn't
impose a specific setting. Remove the hardcoded cave themes. The seed
data in `seed_data.py` already has its own themed content — that's the
right place for opinionated defaults, not the auto-populate function.

## Files Affected

- `src/services/game_logic.py`

## Acceptance Criteria

- [ ] `auto_populate_storylets` accepts an optional `world_bible` parameter
- [ ] When no bible is provided, generated storylets are setting-neutral
- [ ] The hardcoded cave/mine themes are removed from the function
