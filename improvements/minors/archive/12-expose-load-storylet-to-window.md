# Expose loadStorylet to window for spatial navigation refresh

## Problem

In `twine_resources/WorldWeaver-Twine-Story.twee`, `loadStorylet()` is defined
inside an IIFE in the Game passage (~line 285) and is never assigned to
`window`. However, `SpatialNavigation.moveInDirection()` checks
`window.loadStorylet` on line ~608 to refresh the storylet after movement:

```js
if (window.loadStorylet) {
    setTimeout(window.loadStorylet, 1000);
}
```

This condition is **always false**, so after spatial navigation movement the
storylet content never refreshes — the player sees stale content from the
previous location.

## Proposed Fix

Add `window.loadStorylet = loadStorylet;` inside the IIFE, right after the
function definition (~line 330).

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee`

## Acceptance Criteria

- [ ] `window.loadStorylet` is a callable function after the Game passage
      loads.
- [ ] Moving via the spatial compass triggers a storylet refresh showing
      content for the new location.
