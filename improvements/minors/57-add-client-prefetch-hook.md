# Add client-side frontier prefetch hook with debounce and cancellation

## Problem
Even if the server supports frontier prefetch, the client must trigger it in moments that hide latency (after render, during reading, during typing). Without a hook, prefetch won't run predictably.

## Proposed Solution
Add a client hook that:
- triggers prefetch after scene render with a short debounce,
- triggers prefetch while the player is typing (idle-based),
- cancels pending triggers on session reset or navigation,
- silently ignores failures.

## Files Affected
- `client/src/hooks/usePrefetchFrontier.ts` (new)
- `client/src/App.tsx` (wire hook into lifecycle)
- `client/src/api/wwClient.ts` (add `postPrefetchFrontier`, `getPrefetchStatus`)

## Acceptance Criteria
- [ ] Prefetch is triggered after a scene resolves (debounced).
- [ ] Prefetch is triggered during typing when idle threshold is exceeded.
- [ ] Triggers are canceled on session reset.
- [ ] Client remains usable if the endpoint is missing/disabled.
