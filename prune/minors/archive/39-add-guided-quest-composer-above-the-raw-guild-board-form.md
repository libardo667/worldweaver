> **STATUS: CLOSED 2026-06-11 — superseded by Major 68 (guild removal).** This is a
> guild-era item; Major 68 extracts and removes all guild references and affordances, so the
> surface this item authors for no longer exists. Closed under 68 per the 2026-06-11 direction
> review (§2). Archived (not deleted) for record; reinstate only if the guild is ever revived.

# Add a guided quest composer above the raw guild board form

## Problem

[`worldweaver_engine/client/src/components/GuildBoard.tsx`](worldweaver_engine/client/src/components/GuildBoard.tsx)
currently exposes quest assignment primarily as a raw structured form.

That is efficient for the person who designed the system. It is not the best
entry point for a human who wants to contribute one thoughtful quest but does
not yet think in terms of:

- objective type
- target location/person/item
- branch
- quest band
- success signal encoding

The result is that the product becomes harder exactly when a user tries to do
useful work for the commons.

## Proposed Solution

Add a guided quest composer above the raw form in `GuildBoard.tsx`.

The composer should lead with contributor-language rather than system-language:

- What kind of quest is this?
- Who is it for?
- Where should it pull them?
- What should they have to notice, verify, deliver, repair, or complete?
- What evidence would show the quest worked?

The composer should produce the same structured payloads the current form
already uses. The raw form should remain accessible as an advanced mode for
power users.

## Files Affected

- `worldweaver_engine/client/src/components/GuildBoard.tsx`
- `worldweaver_engine/client/src/types.ts`
- `worldweaver_engine/client/src/styles.css`

## Acceptance Criteria

- [x] The first quest-authoring experience is a guided composer rather than a raw field dump
- [x] The guided composer maps cleanly onto the existing quest assignment payload without inventing a separate backend contract
- [x] Contributors can still switch to a raw or advanced form when they want direct control
- [x] The composer reduces the amount of guild-specific jargon shown before a contributor has chosen the quest they want to make
