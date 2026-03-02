# Fix broken toggleFullscreen no-op in reality map

## Problem

`WorldWeaver.map.toggleFullscreen()` in
`twine_resources/WorldWeaver-Twine-Story.twee` (~lines 1200–1221) has a
logic bug. The "exit fullscreen" branch checks
`overlay.style.position === 'fixed'` and then **sets it to `'fixed'` again** —
a complete no-op:

```js
if (overlay.style.position === 'fixed') {
    // "Exit fullscreen" — but this just re-sets the same values
    overlay.style.position = 'fixed';
    overlay.style.width = '100%';
    overlay.style.height = '100%';
    // ...
}
```

The condition is always true (the overlay is created with `position: fixed`),
so the `else` branch (which calls `requestFullscreen()`) is never reached.

## Proposed Fix

Replace the broken conditional with a proper Fullscreen API toggle:

```js
toggleFullscreen: function() {
    if (document.fullscreenElement) {
        document.exitFullscreen();
    } else {
        const overlay = document.getElementById('reality-map-overlay');
        if (overlay) overlay.requestFullscreen();
    }
}
```

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee`

## Acceptance Criteria

- [ ] Clicking the fullscreen toggle button enters browser fullscreen mode.
- [ ] Clicking it again (or pressing Escape) exits fullscreen.
