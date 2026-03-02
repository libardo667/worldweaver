# Build an API-first web client v1 for WorldWeaver

## Problem
WorldWeaver currently has a backend prototype and a Twine-based prototype UI, but no purpose-built player interface that makes the dual-layer experience (physical navigation + narrative evolution) feel natural. Without a dedicated client, it is difficult to:
- keep “Now / Place / Memory” visible at once,
- support freeform actions as a first-class control,
- give immediate consequence legibility (“what changed”),
- make the world’s history and facts explorable without developer tools.

## Proposed Solution
Create a minimal, API-first web client (v1) that talks only to existing endpoints and makes **Explore mode** playable.

Scope: Explore mode only. Reflect/Create/Constellation are separate majors.

Implementation outline:
1. Add a new `client/` directory with a small web app (recommended: Vite + React + TypeScript, but a vanilla JS build is acceptable if preferred).
2. Implement the core layout:
   - Center **Now** panel (scene text + choices).
   - Always-visible **Freeform input** (POST `/api/action`).
   - Right **Place** panel (location card + time/weather badges + 3×3 compass).
   - Left **Memory** panel (recent events + world-facts search).
   - Collapsible **What changed** strip computed by client-side diffing of session vars and last action/choice sets.
3. Implement a simple API client wrapper:
   - POST `/api/next` with `session_id` and `vars`.
   - POST `/api/action` with freeform action text.
   - GET `/api/spatial/navigation/{session_id}` and POST `/api/spatial/move/{session_id}` for compass movement.
   - GET `/api/world/history` and GET `/api/world/facts?query=...` for memory panel.
4. Session handling:
   - Generate a session id on first load; persist to `localStorage`.
   - Keep a local copy of session vars; send them in `/api/next` calls.
5. Error handling + UX:
   - If endpoints return errors, show an in-world styled error toast and allow retry.
   - Provide a “Reset session” button that clears local state and selects a new session id.

Recommended file structure (example):
- `client/`
  - `src/api/wwClient.ts`
  - `src/state/sessionStore.ts`
  - `src/components/NowPanel.tsx`
  - `src/components/ChoiceButtons.tsx`
  - `src/components/FreeformInput.tsx`
  - `src/components/PlacePanel.tsx`
  - `src/components/Compass.tsx`
  - `src/components/MemoryPanel.tsx`
  - `src/components/WhatChangedStrip.tsx`
  - `src/App.tsx`
  - `src/main.tsx`

## Files Affected
- client/ (new)
- client/src/api/wwClient.ts (new)
- client/src/state/sessionStore.ts (new)
- client/src/components/* (new)
- client/README.md (new)
- (Optional) docs or root README to link to client dev commands

## Acceptance Criteria
- [x] A player can load the client, get an initial scene, and see 2–6 choice buttons.
- [x] Clicking a choice updates local vars and requests the next scene via POST `/api/next`.
- [x] The freeform input sends POST `/api/action` and renders the returned narrative and follow-up choices.
- [x] The Place panel renders a 3×3 compass and successfully moves using `/api/spatial/*` endpoints.
- [x] The Memory panel renders recent history from `/api/world/history` and supports search via `/api/world/facts`.
- [x] The What changed strip displays at least one human-readable change after a choice or action (computed client-side).
- [x] Session id persists across reloads and the same session continues (localStorage).
- [x] `pytest -q` still passes in the backend repo (client is additive only).

## Risks & Rollback
Primary risks:
- Frontend scope creep (turning v1 into a full product surface prematurely).
- Accidental API coupling (client assumes behaviors not guaranteed by the API).
- Styling churn (large diffs from repeated UI iteration).

Rollback:
- This is additive. If needed, delete `client/` and remove any README links. Backend remains unchanged.
