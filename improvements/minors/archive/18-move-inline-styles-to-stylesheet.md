# Move inline styles from JavaScript to stylesheet passage

## Problem

`twine_resources/WorldWeaver-Twine-Story.twee` contains large blocks of inline
CSS set via `element.style.cssText` in JavaScript, particularly in the
`WorldWeaver.ui` and `WorldWeaver.map` sections:

- `addCosmicParticles()` (~lines 717–732) — 12-line `cssText` block
- `showProgressIndicator()` (~lines 754–765) — 10-line `cssText` block
- `createMapToggle()` (~lines 797–813) — 13-line `cssText` block
- `showRealityMap()` overlay (~lines 1081–1091) — 9-line `cssText` block
- `showRealityMap()` container (~lines 1094–1102) — 8-line `cssText` block
- Close button (~lines 1106–1119) — 10-line `cssText` block

These styles are duplicated on every function call, are hard to maintain, and
cannot be overridden by theme changes.

## Proposed Fix

Move all inline `cssText` blocks to CSS classes in the `Story Stylesheet`
passage, then apply the classes in JavaScript via `classList.add()`:

```js
// Before
indicator.style.cssText = `position: fixed; top: 10px; ...`;

// After
indicator.classList.add('progress-indicator');
```

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee`

## Acceptance Criteria

- [ ] No multi-line `style.cssText` assignments remain in JavaScript.
- [ ] All dynamically created elements use CSS classes from the stylesheet.
- [ ] Visual appearance is unchanged.
