# Fix hardcoded 'forest' default in ensureLocation

## Problem

`SpatialNavigation.ensureLocation()` in
`twine_resources/WorldWeaver-Twine-Story.twee` (~line 476) defaults to
`'forest'` when no location is set:

```js
const initialLoc = (typeof State !== 'undefined' && State.variables && State.variables.location)
    ? State.variables.location
    : 'forest';
```

This is incorrect when the player has generated a custom world (e.g. "Cosmic
Storms" or "Quantum Echoes") that may not contain a location called "forest".
The backend will either fail to find any storylet at that location or silently
pick a storylet that doesn't match the world.

## Proposed Fix

Remove the hardcoded `'forest'` fallback. Instead:

1. Let the backend decide the starting location — omit the `location` var from
   the initial `POST /api/next` call if none is set. The backend's
   `pick_storylet` already handles missing location by selecting from all
   available storylets.
2. After the first `/api/next` response, read the location from the response
   vars and store it for subsequent navigation.

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee`

## Acceptance Criteria

- [ ] The string `'forest'` does not appear as a fallback location in the
      `.twee` file.
- [ ] A freshly generated world with no "forest" location initialises spatial
      navigation without errors.
