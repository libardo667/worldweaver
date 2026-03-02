# Add compass widget and keyboard navigation bindings

## Problem
Spatial navigation is central to the physical-layer experience, but clicking small targets can be slow and accessibility-unfriendly. Keyboard bindings make exploration faster and more game-like.

## Proposed Solution
Add:
- a compact 3×3 compass widget with accessible buttons,
- keyboard navigation:
  - arrow keys for N/S/E/W,
  - shift+arrow for diagonals (or WASD/QEZX),
  - enter to focus freeform input.

The compass uses existing endpoints:
- GET `/api/spatial/navigation/{session_id}`
- POST `/api/spatial/move/{session_id}`

## Files Affected
- client/src/components/Compass.tsx
- client/src/hooks/useKeyboardNavigation.ts (new)
- client/src/api/wwClient.ts

## Acceptance Criteria
- [x] Compass buttons reflect accessibility (disabled state when movement blocked).
- [x] Keyboard bindings trigger movement and update location consistently.
- [x] No backend changes required.
