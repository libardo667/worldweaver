# Add a compact progressive loading indicator and keep-last-scene behavior

## Problem
When a turn is slow, the UI can feel frozen or blank. Players need a clear "something is happening" signal without losing their place.

## Proposed Solution
Implement:
- keep the last scene visible during pending state,
- add a compact phase indicator (e.g., "Interpreting / Rendering / Weaving ahead"),
- show streaming shimmer only in the text area (no whole-page overlays),
- never steal focus from the freeform input.

## Files Affected
- `client/src/components/NowPanel.tsx`
- `client/src/components/FreeformInput.tsx`
- `client/src/styles.css`
- `client/src/App.tsx` (phase state)

## Acceptance Criteria
- [x] Pending actions keep the prior scene visible.
- [x] A small loading indicator is shown without layout jumps.
- [x] Streaming updates do not scroll-jank the page.
- [x] Input focus is preserved.
