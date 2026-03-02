# Extract hardcoded backend URL into a configurable base

## Problem

The Twine frontend (`twine_resources/WorldWeaver-Twine-Story.twee`) hardcodes
`http://localhost:8000` in **10+ separate `fetch()` calls** across the
`WorldBuilder`, `Game`, and `StoryScript` passages. This means:

- Deploying to any environment other than local dev requires manually editing
  every occurrence.
- A single missed occurrence silently breaks one feature while the rest work.
- There is no way for the Twine story to discover the backend URL at runtime.

Affected lines (approximate): 152, 287, 350, 405–406, 478, 496, 567, 1256.

## Proposed Solution

1. **Define a single `API_BASE` constant** at the top of the `StoryScript`
   passage:

   ```js
   window.API_BASE = window.API_BASE
       || localStorage.getItem('worldweaver_api_base')
       || 'http://localhost:8000';
   ```

   This allows override via a global, localStorage setting, or falls back to
   the current default.

2. **Replace every `fetch('http://localhost:8000/...')` call** with
   `` fetch(`${API_BASE}/...`) ``.

3. **Add a small "Server Settings" UI** in the `Start` passage (or a new
   `Settings` passage) that lets the user view/change the backend URL and
   persists it to `localStorage`.

4. **Optionally add a connectivity check** on startup that pings `/health`
   and shows a warning banner if the backend is unreachable.

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee`

## Acceptance Criteria

- [ ] `http://localhost:8000` appears exactly **zero** times in the `.twee`
      file (outside of comments or documentation).
- [ ] All API calls use the `API_BASE` variable.
- [ ] Changing `localStorage.worldweaver_api_base` before loading the story
      causes all fetches to target the new URL.
- [ ] The default behaviour (`http://localhost:8000`) is preserved when no
      override is set.

## Risks & Rollback

Low risk — purely a client-side refactor. If the constant is wired incorrectly,
API calls will 404 immediately and the issue will be obvious. Rollback is a
single-file revert.
