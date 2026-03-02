# Mobile and accessibility pass for the web client

## Problem
A narrative interface lives or dies on readability and low-friction controls. Without an accessibility and mobile pass, the UI will feel brittle and exclude keyboard/screen-reader users.

## Proposed Solution
Implement an accessibility + mobile usability pass:
- Ensure readable font sizes and line lengths.
- Add focus rings and sensible tab order.
- Add ARIA labels for compass and choice buttons.
- Ensure sufficient contrast for text and controls.
- Provide mobile-friendly panel toggles (tabs/drawers) and avoid tiny click targets.

## Files Affected
- client/src/styles.css (or equivalent)
- client/src/layout/AppShell.tsx
- client/src/components/Compass.tsx
- client/src/components/ChoiceButtons.tsx
- client/src/components/FreeformInput.tsx

## Acceptance Criteria
- [x] UI is usable on small screens without horizontal scrolling.
- [x] All interactive controls are keyboard-navigable.
- [x] Compass and choices have ARIA labels and clear focus states.
- [x] No backend changes required.
