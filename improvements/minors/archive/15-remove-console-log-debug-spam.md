# Remove excessive console.log debug spam

## Problem

`twine_resources/WorldWeaver-Twine-Story.twee` contains **25+ `console.log()`
calls** with emoji prefixes throughout the `StoryScript` and `Game` passages.
These were useful during initial development but are noise in production:

Examples:
- `console.log('✅ SpatialNavigation object loaded!', window.SpatialNavigation);`
- `console.log('🔍 Checking for navigation elements...');`
- `console.log('📡 Loading navigation data for session:', this.sessionId);`
- `console.log('🗺️ Navigation data received:', data);`

Some of these also log potentially sensitive data (full navigation objects,
session IDs).

## Proposed Fix

1. Remove all `console.log()` calls that are pure development tracing.
2. Keep `console.error()` and `console.warn()` calls that report actual
   failures.
3. Optionally gate remaining debug output behind a
   `localStorage.getItem('worldweaver_debug')` flag.

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee`

## Acceptance Criteria

- [ ] No `console.log()` calls remain that output routine tracing info.
- [ ] `console.error()` / `console.warn()` for genuine error conditions are
      preserved.
- [ ] The browser console is clean during normal gameplay.
