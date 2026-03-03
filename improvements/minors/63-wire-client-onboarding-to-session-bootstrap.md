# Wire client onboarding to session bootstrap

## Problem
The onboarding form stores `world_theme` and `player_role`, but "Start this world" currently transitions by local var merge and `/api/next` bootstrap (`client/src/App.tsx:531-546`, `client/src/App.tsx:218-223`, `client/src/App.tsx:238-250`). There is no dedicated bootstrap API call to initialize world content before first scene selection.

## Proposed Solution
1. Add a client API call for `POST /api/session/bootstrap` in `client/src/api/wwClient.ts`.
2. Update onboarding submit flow in `client/src/App.tsx`:
   - submit onboarding payload to bootstrap endpoint,
   - persist bootstrap-returned vars/session metadata,
   - only then trigger first `/api/next`.
3. Keep onboarding UI active on bootstrap failure and display a clear error toast without partial transition.

## Files Affected
- `client/src/App.tsx`
- `client/src/api/wwClient.ts`
- `client/src/state/sessionStore.ts`
- `client/src/types.ts` (if bootstrap response typing is added)

## Acceptance Criteria
- [ ] Clicking "Start this world" calls session bootstrap before first `/api/next`.
- [ ] On bootstrap failure, onboarding remains visible and play does not advance.
- [ ] Bootstrap-returned session vars are persisted to client state before first scene render.
- [ ] `npm --prefix client run build` passes.
