# Add connection resilience and graceful error handling to the Twine frontend

## Problem

When the backend server is down or slow, the Twine story displays raw
`Error: Failed to fetch` or `TypeError: Failed to fetch` messages directly in
the game UI via `innerHTML`. There is:

- **No retry logic** — a single transient failure kills the session.
- **No user-friendly error states** — the player sees developer-facing text.
- **No timeout** — `fetch()` calls can hang indefinitely on a slow backend.
- **No offline detection** — the story never checks `navigator.onLine`.

Affected locations in `twine_resources/WorldWeaver-Twine-Story.twee`:
- `generateWorld()` (~line 193–195)
- `loadStorylet()` (~line 326–329)
- `makeChoice()` (~line 379–382)
- `SpatialNavigation.loadNavigation()` (~line 506–509)
- `SpatialNavigation.moveInDirection()` (~line 618–620)

## Proposed Solution

1. **Create a shared `apiFetch()` wrapper** in the `StoryScript` passage that:
   - Adds a configurable timeout (default 15 s) via `AbortController`.
   - Retries transient failures (network errors, 502/503/504) up to 2 times
     with exponential backoff.
   - Returns a structured `{ ok, data, error }` result instead of throwing.

2. **Replace all raw `fetch()` calls** with `apiFetch()`.

3. **Add user-friendly error templates** — e.g. "The server is not responding.
   Please make sure the backend is running and try again." with a retry button,
   instead of raw `error.message`.

4. **Add an offline banner** that listens to `window.addEventListener('offline')`
   and shows a non-intrusive notice.

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee`

## Acceptance Criteria

- [ ] All `fetch()` calls go through the shared wrapper.
- [ ] A 15-second timeout is enforced on every API call.
- [ ] Transient failures are retried up to 2 times before showing an error.
- [ ] Error messages shown to the player are human-readable (no raw JS errors).
- [ ] Each error state includes a "Retry" button.
- [ ] Going offline shows a visible indicator; coming back online hides it.

## Risks & Rollback

Medium risk — the retry wrapper must correctly propagate non-retryable errors
(e.g. 422 validation). Incorrect retry logic could cause duplicate world
generation. Rollback is a single-file revert.
