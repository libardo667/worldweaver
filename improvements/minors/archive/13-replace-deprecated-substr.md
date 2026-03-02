# Replace deprecated substr with substring

## Problem

`twine_resources/WorldWeaver-Twine-Story.twee` uses `String.prototype.substr()`
in two locations:

- Line ~280: `Math.random().toString(36).substr(2, 9)` (session ID generation)
- Line ~1241: `Math.random().toString(36).substr(2, 9)` (progress reset)

`substr()` is deprecated in the ECMAScript specification (Annex B) and may be
removed from non-browser environments. Modern code should use `substring()` or
`slice()`.

## Proposed Fix

Replace both occurrences:

```js
// Before
Math.random().toString(36).substr(2, 9)

// After
Math.random().toString(36).substring(2, 11)
```

Note: `substr(2, 9)` means "start at index 2, take 9 characters" while
`substring(2, 11)` means "from index 2 to index 11 (exclusive)" — same result.

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee`

## Acceptance Criteria

- [ ] Zero occurrences of `.substr(` in the `.twee` file.
- [ ] Generated session IDs remain 9-character alphanumeric strings.
