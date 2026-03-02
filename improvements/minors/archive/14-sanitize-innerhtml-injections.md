# Sanitize dynamic content injected via innerHTML

## Problem

`twine_resources/WorldWeaver-Twine-Story.twee` injects untrusted content
directly into `innerHTML` without escaping in several places:

1. **Error messages** (~lines 328, 381): `error.message` is interpolated
   directly:
   ```js
   `<p>Error loading reality: ${error.message}</p>`
   ```

2. **Backend storylet text** (~lines 307, 362): `story.text` from the API
   is injected raw:
   ```js
   let html = `<p>${story.text}</p>`;
   ```

3. **Choice labels** (~lines 312, 367): `choice.label` is injected into
   button text.

If the backend returns malicious or malformed HTML/JS in storylet text or
choice labels, it will execute in the player's browser (XSS).

## Proposed Fix

Add a small `escapeHTML()` utility:

```js
function escapeHTML(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}
```

Apply it to all dynamic string interpolations into `innerHTML`: `story.text`,
`choice.label`, and `error.message`.

## Files Affected

- `twine_resources/WorldWeaver-Twine-Story.twee`

## Acceptance Criteria

- [ ] An `escapeHTML` (or equivalent) utility exists in the StoryScript.
- [ ] `story.text`, `choice.label`, and `error.message` are escaped before
      `innerHTML` insertion.
- [ ] A storylet containing `<script>alert(1)</script>` in its text renders
      as visible text, not executable code.
