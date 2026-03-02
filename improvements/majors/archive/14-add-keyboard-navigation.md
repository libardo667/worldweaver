# Add keyboard navigation and accessibility to the Twine frontend

## Problem

The spatial compass and game choices in `twine_resources/WorldWeaver-Twine-Story.twee`
are **mouse-only**. There are no keyboard shortcuts, no ARIA attributes, and no
focus management:

- The 3×3 compass grid cells are `<div>` elements with `click` handlers — not
  focusable, not keyboard-operable.
- Choice buttons are `<button>` elements (good) but have no number-key
  shortcuts.
- The reality map overlay has no `Escape` key to close.
- Screen readers get no context about compass directions, game state, or
  available choices.

## Proposed Solution

1. **Add `tabindex="0"` and `role="button"`** to all `.nav-cell` divs.
   Add `aria-label` attributes (e.g. `aria-label="Move northwest"`).

2. **Add keyboard event listener** for spatial navigation:
   - Numpad 1–9 or arrow keys → compass directions
   - `1`–`4` number keys → select choice by index
   - `Escape` → close reality map overlay
   - `M` → toggle reality map

3. **Add visible focus indicators** (`:focus-visible` outline) to nav cells
   and choice buttons in the stylesheet.

4. **Add `aria-live="polite"` region** for the `#game-content` div so screen
   readers announce new storylet text.

5. **Add `role="navigation"` and `aria-label`** to the spatial compass
   container.

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee` (StoryScript + Game passage +
  Story Stylesheet)

## Acceptance Criteria

- [ ] All 8 compass directions are reachable and activatable via keyboard.
- [ ] Number keys 1–4 select the corresponding game choice.
- [ ] `Escape` closes the reality map overlay.
- [ ] Compass cells and choice buttons show a visible focus ring on
      `:focus-visible`.
- [ ] The game content area has `aria-live="polite"`.
- [ ] The compass has `role="navigation"` with a descriptive `aria-label`.

## Risks & Rollback

Low risk — additive changes only. Keyboard shortcuts could conflict with
SugarCube's built-in bindings, but SugarCube 2.x has minimal default key
bindings. Rollback is a single-file revert.
