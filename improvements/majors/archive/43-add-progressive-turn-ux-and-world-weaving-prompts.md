# Add progressive turn UX with background world-building prompts

## Problem
Even with streaming, long turns can feel like a "dead air" wait. Players need a continuously responsive UI that:
- acknowledges intent immediately,
- shows progress and partial meaning quickly,
- keeps them engaged during slow-lane world building (optional prompts),
- makes it clear the world is expanding around them.

## Proposed Solution
Implement a progressive UX that blends:
- multi-phase streaming (ack → core outcome → deepening),
- "busy hands" prompts during onboarding and long turns,
- client-side prefetch triggers that populate the frontier cache.

1. Progressive rendering for turns
   - Maintain the previous scene visible while a new turn resolves.
   - Show a compact "Weaving..." indicator with a phase label:
     - "Interpreting" (intent),
     - "Confirming" (validator / state commit),
     - "Rendering" (narration),
     - "Weaving ahead" (background prefetch).
   - Stream draft text into the Now panel while preserving a stable scroll position.

2. World-weaving prompts during onboarding and long turns
   - After the initial two onboarding answers (theme + role), offer 1–3 optional prompts while background prefetch runs:
     - "What do you notice first?"
     - "Name one hope."
     - "Name one fear."
     - "Pick a vibe lens (cozy/tense/uncanny/hopeful)."
   - Submitting a prompt updates session vars (preferences/lenses) and can influence prefetch generation without blocking play.

3. Client-side prefetch triggers
   - After any scene render, schedule a prefetch trigger after a short idle delay (debounced).
   - When the player is typing in the freeform input, trigger prefetch if idle for N seconds.
   - Prefetch triggers should be best-effort and cancelable; they must not interrupt play.

4. Lightweight prefetch status
   - Show "Frontier cached: X stubs" in the Place or Memory panel (debug-friendly).
   - This can be hidden behind a client feature flag in v1.

## Files Affected
- `client/src/App.tsx` (progressive turn state machine + prefetch trigger hooks)
- `client/src/components/NowPanel.tsx` (streamed text + pending overlay)
- `client/src/components/FreeformInput.tsx` (typing-idle signal)
- `client/src/components/WhatChangedStrip.tsx` (phase-aware updates)
- `client/src/components/SetupOnboarding.tsx` (new, optional: world-weaving prompts)
- `client/src/hooks/usePrefetchFrontier.ts` (new)
- `client/src/types.ts` (optional: prefetch status shape)
- (Backend) `src/api/game/prefetch.py` (if a dedicated trigger/status endpoint is introduced)

## Acceptance Criteria
- [x] While a turn resolves, the previous scene remains visible and the UI indicates the current phase.
- [x] Streaming updates appear smoothly without causing layout jumps or losing input focus.
- [x] Optional world-weaving prompts can be shown during onboarding and can update session vars.
- [x] The client triggers background prefetch after scene render and during typing-idle, without blocking play.
- [x] Prefetch failures are silent and only show a small toast at most.
- [x] `npm run build` succeeds for the client.

## Risks & Rollback
Overly busy UI can reduce readability. Keep indicators compact and collapseable. Roll back by disabling progressive phases and prompts behind a feature flag while leaving baseline Explore intact.
