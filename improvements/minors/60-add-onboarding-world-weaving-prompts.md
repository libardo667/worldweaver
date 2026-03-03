# Add onboarding world-weaving prompts that run while prefetch warms the frontier

## Problem
Initial world generation can be slow and feels like "waiting for the game to start." Players are more patient if the UI asks playful, meaningful questions that also improve the world seed.

## Proposed Solution
After the core onboarding (theme + role), add 1–3 optional prompts that can be answered while prefetch runs:
- first impression (1 sentence),
- hope,
- fear,
- optional vibe lens selection.

These update session vars and can influence subsequent prefetch/storylet synthesis.

## Files Affected
- `client/src/App.tsx` (onboarding flow)
- `client/src/components/SetupOnboarding.tsx` (new or extend existing onboarding UI)
- `client/src/state/sessionStore.ts` (persist new vars)
- `client/src/api/wwClient.ts` (ensure vars sent to `/api/next`)

## Acceptance Criteria
- [ ] Prompts are optional and skippable; play can start immediately.
- [ ] Prompt answers persist in session vars and influence subsequent turns.
- [ ] Prefetch is triggered during onboarding and does not block scene rendering.
