# Replace alert() calls with styled modal dialogs

## Problem

`twine_resources/WorldWeaver-Twine-Story.twee` uses browser `alert()` and
`confirm()` in several places:

- Line ~141: `alert('Please fill in the world description and theme!');`
- Line ~1154: `alert(...)` in `showThreadDetail()` — shows journey step info
- Line ~1191: `confirm(...)` in `clearMap()`
- Line ~1196: `alert('✅ Reality thread history cleared!')`
- Line ~1251: `confirm(...)` in `cleanupSessions()`
- Line ~1263–1265: `alert(...)` for cleanup results

Native `alert()`/`confirm()` dialogs block the JS thread, look jarring against
the polished cosmic UI, cannot be styled, and break immersion.

## Proposed Fix

Replace each `alert()`/`confirm()` with a lightweight modal function that
renders an in-page dialog using the existing glassmorphic styling. A simple
implementation:

```js
WorldWeaver.ui.showModal = function(message, { onConfirm, onCancel } = {}) {
    // Render a styled overlay with message + OK/Cancel buttons
};
```

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee`

## Acceptance Criteria

- [ ] Zero occurrences of `alert(` or `confirm(` in the `.twee` file.
- [ ] Modal dialogs match the cosmic/glassmorphic visual style.
- [ ] Confirmation modals resolve a promise or call a callback on user action.
