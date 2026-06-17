> **STATUS: CLOSED 2026-06-11 — superseded by Major 68 (guild removal).** This is a
> guild-era item; Major 68 extracts and removes all guild references and affordances, so the
> surface this item authors for no longer exists. Closed under 68 per the 2026-06-11 direction
> review (§2). Archived (not deleted) for record; reinstate only if the guild is ever revived.

# Reframe guild contributor onboarding around apprentice-first participation

## Problem

The product currently risks asking for too much identity and commitment too
early when guild work enters the picture.

Even when the entry threshold itself has improved, guild participation can still
feel like:

- become a mentor
- accept governance language
- create an account before knowing whether you want to contribute

That framing is heavier than necessary. Many potential contributors are more
likely to try one useful act of contribution than to opt into a role identity
up front.

## Proposed Solution

Reframe the guild contribution path around apprentice-first participation.

The frontend should make the first ask:

- contribute a quest idea
- draft a quest
- complete a low-commitment contribution step

Mentor language should arrive later, after the user has already contributed and
understands the kind of work the guild actually does.

This does not remove mentor and steward roles. It changes the sequence so
contribution precedes status.

## Files Affected

- `worldweaver_engine/client/src/components/EntryFlow.tsx`
- `worldweaver_engine/client/src/components/AuthScreen.tsx`
- `worldweaver_engine/client/src/components/ParticipationModeScreen.tsx`
- `worldweaver_engine/client/src/components/GuildBoard.tsx`
- `worldweaver_engine/client/src/styles.css`

## Acceptance Criteria

- [x] Guild contribution copy emphasizes apprentice or contributor participation before mentor identity
- [x] The UI no longer makes "be a mentor" feel like the first or only meaningful guild entry point
- [x] Contributors can understand the work of quest creation before being asked to internalize rank and governance language
- [x] Mentor and steward capabilities remain available, but are framed as earned or advanced participation rather than default threshold identity
