# Deduplicate storylet rendering logic in the Twine frontend

## Problem

The storylet-to-HTML rendering code is **copy-pasted in two places** in
`twine_resources/WorldWeaver-Twine-Story.twee`:

1. `loadStorylet()` (~lines 306–324) — initial load
2. `makeChoice()` (~lines 361–377) — after a choice is made

Both do the same thing: check `story.text`, build choice buttons with
`onclick="makeChoice(${index})"`, set `innerHTML`, and store
`window.currentChoices` / `window.currentVars`. Any fix to one must be
manually replicated to the other.

Additionally, `loadStorylet()` is defined inside an IIFE and never exposed to
`window`, yet line ~608 checks `if (window.loadStorylet)` for the spatial
navigation refresh — which always fails.

## Proposed Solution

1. **Extract a shared `renderStorylet(story)` function** that takes the API
   response and returns an HTML string (or directly updates `#game-content`).

2. **Expose `loadStorylet` to `window`** so `SpatialNavigation.moveInDirection`
   can trigger a storylet refresh after movement.

3. **Call `renderStorylet` from both `loadStorylet` and `makeChoice`**,
   eliminating the duplication.

4. **Move `window.currentChoices` and `window.currentVars` assignments** into
   `renderStorylet` so they are always in sync.

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee`

## Acceptance Criteria

- [ ] Storylet rendering logic exists in exactly one place.
- [ ] `loadStorylet` and `makeChoice` both delegate to the shared renderer.
- [ ] `window.loadStorylet` is callable — spatial navigation movement triggers
      a storylet refresh.
- [ ] No behavioural change from the player's perspective.

## Risks & Rollback

Low risk — purely a refactor within one file. If the shared function signature
is wrong, storylets will fail to render, which is immediately visible. Rollback
is a single-file revert.
