# Add Create mode preference controls and narrative-beat lenses

## Problem
Players need a gentle, non-technical way to steer the experience without authoring a story tree. Without Create mode controls:
- tone can drift unpredictably,
- safety boundaries are unclear,
- “surprise me (safe)” and other diversity operators are not player-addressable.

## Proposed Solution
Add a lightweight Create mode in the client that writes preferences into session variables and displays what is active.

Client-first approach (backend unchanged for v1):
1. Add a mode toggle: Explore | Reflect | Create.
2. Create mode UI includes:
   - tone selectors (cozy / tense / uncanny / hopeful),
   - content boundaries (violence low/medium/high; romance off/on),
   - “Surprise me (safe)” button (sends a standardized freeform action to `/api/action` plus sets a `surprise_safe=true` var).
3. Persist preferences in session vars with a dedicated namespace:
   - `pref.tone`, `pref.violence`, `pref.romance`, `lens.community`, `lens.mystery`, etc.
4. Each `/api/next` and `/api/action` request includes the current preference vars.

Optional backend enhancement (still additive):
- Update prompt builders to include preference vars when present (LLM-side steering only; does not change state rules).

Recommended client files:
- `client/src/views/CreateView.tsx`
- `client/src/components/PreferenceControls.tsx`
- `client/src/components/LensSliders.tsx`

## Files Affected
- client/src/App.tsx (modify: mode toggle includes Create)
- client/src/views/CreateView.tsx (new)
- client/src/components/PreferenceControls.tsx (new)
- client/src/components/LensSliders.tsx (new)
- (Optional) src/services/command_interpreter.py (modify: include preferences in prompt if present)

## Acceptance Criteria
- [ ] Create mode is reachable from the client and does not reset the session.
- [ ] Preferences persist across reloads (stored locally and mirrored into session vars sent to API).
- [ ] “Surprise me (safe)” triggers a freeform action and renders results in Explore mode.
- [ ] No backend route or payload changes are required for the client-only version.
- [ ] Existing backend tests remain green (`pytest -q`).

## Risks & Rollback
Primary risks:
- Player expects stronger guarantees than preference steering can provide (make UI copy clear: “steers, doesn’t dictate”).
- Prompt steering reduces creativity if over-weighted (keep defaults mild).
- Preferences sprawl (limit v1 to a small set).

Rollback:
- Hide Create mode behind a client feature flag or remove Create view files. Backend unchanged.
