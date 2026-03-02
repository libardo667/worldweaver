# Log skipped storylets in save_storylets_with_postprocessing

## Problem

`src/api/author.py` `save_storylets_with_postprocessing` lines ~59-63
silently skips storylets that are missing any of the 5 required keys
(`title`, `text_template`, `choices`, `requires`, `weight`). The caller
gets back `added: N` with a lower count than expected and no explanation
of why storylets were dropped.

## Proposed Fix

Add a `logger.warning` call when a storylet is skipped, including the
storylet's title (if present) and which required key was missing. Also
return the skip count in the response so the caller knows.

## Files Affected

- `src/api/author.py`

## Acceptance Criteria

- [ ] Skipped storylets produce a warning log with the reason
- [ ] The response includes a `skipped` count alongside `added`
