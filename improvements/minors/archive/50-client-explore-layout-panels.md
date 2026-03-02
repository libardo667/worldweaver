# Implement the Explore mode three-panel layout

## Problem
Explore mode needs a stable visual grammar (Now/Place/Memory) to prevent the world from feeling like a scrolling chat log. Without a consistent layout, navigation and memory feel buried.

## Proposed Solution
Implement a responsive three-panel layout in the client:
- Center: Now panel (scene + choices + freeform input).
- Left: Memory panel (recent events + search).
- Right: Place panel (location + compass + POIs).
Responsive rules:
- Desktop: three columns.
- Mobile: Now panel primary; Place/Memory collapse into tabs or drawers.

## Files Affected
- client/src/App.tsx
- client/src/layout/AppShell.tsx (new)
- client/src/components/NowPanel.tsx
- client/src/components/PlacePanel.tsx
- client/src/components/MemoryPanel.tsx
- client/src/styles.css (or equivalent)

## Acceptance Criteria
- [x] Explore mode renders three panels on desktop widths and remains usable on mobile widths.
- [x] Panels have consistent headers and do not reflow unpredictably as text grows.
- [x] No backend changes required.
