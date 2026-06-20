# Split settings into account, narration, and continuity surfaces

> ⏳ **PARKED, behind Major 43 (2026-06-19).** This item predates the project's shift from a
> multiplayer-game UX toward a research apparatus; its proposed account/narration/continuity split
> assumes a settled human-facing surface that no longer exists. The user-facing direction is unsettled
> and is owned by **Major 43** (`43-rebuild-the-human-front-door-around-curiosity-participation-and-progressive-disclosure.md`):
> a settings re-layout should fall out of that rebuild, not be designed against the current,
> soon-to-change drawer. Related context: **Major 22** (frontend-flow stabilization), **Major 71**
> (the steward-facing portal). Revisit trigger: once Major 43 lands a settled front-door shape, reread
> this and decide whether the account/narration/continuity cut still holds or is superseded by it.
>
> Depends-On: Major 43 (human front-door rebuild).

## Problem

[`worldweaver_engine/client/src/components/SettingsDrawer.tsx`](worldweaver_engine/client/src/components/SettingsDrawer.tsx)
currently bundles together too many different kinds of meaning:

- account identity and pass state
- API key and model/economic controls
- continuity/tether/non-negotiable settings
- leave-world and other consequential actions

That makes the drawer feel emotionally and conceptually dense. It also hides
important distinctions:

- account is not the same as narration
- narration is not the same as continuity
- continuity should feel like a dedicated choice, not incidental drawer clutter

## Proposed Solution

Split the settings surface into at least three clearer sections:

- `account`
  - identity, pass, sign-in state, leave world
- `narration`
  - API key, selected model, cost/readiness information
- `continuity`
  - tethered mode, identity form, non-negotiables, absence semantics

If continuity remains emotionally heavy, it should be promotable into a
dedicated follow-up flow rather than staying trapped as just another drawer tab.

## Files Affected

- `worldweaver_engine/client/src/components/SettingsDrawer.tsx`
- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/api/wwClient.ts`
- `worldweaver_engine/client/src/types.ts`

## Acceptance Criteria

- [ ] Settings no longer present account, model/economic, and continuity controls as one undifferentiated knot
- [ ] Users can understand where to go for account issues versus model narration versus continuity decisions
- [ ] Continuity/tether language becomes less surprising and easier to approach
- [ ] Existing settings functionality remains available after the split
