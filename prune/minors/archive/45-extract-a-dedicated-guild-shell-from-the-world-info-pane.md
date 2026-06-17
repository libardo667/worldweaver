> **STATUS: CLOSED 2026-06-11 — superseded by Major 68 (guild removal).** This is a
> guild-era item; Major 68 extracts and removes all guild references and affordances, so the
> surface this item authors for no longer exists. Closed under 68 per the 2026-06-11 direction
> review (§2). Archived (not deleted) for record; reinstate only if the guild is ever revived.

# Extract a dedicated guild shell from the world info pane

## Problem

[`worldweaver_engine/client/src/components/WorldInfoPane.tsx`](worldweaver_engine/client/src/components/WorldInfoPane.tsx)
is already carrying too many kinds of work:

- map
- presence
- chats
- notes
- guild

That makes the current guild board feel structurally secondary even though guild
contribution is becoming one of the main human loops in the product.

The problem is not just that `GuildBoard.tsx` is visually rough. The problem is
that quest authoring, review, and mentor/steward work live inside a container
built for lightweight world-side inspection.

Guild access already exists as a distinct app entry state. That means the
product does not need to keep guild work inside the world info pane merely for
routing convenience.

## Proposed Solution

Extract guild mode into a dedicated guild shell loaded directly from the
existing guild access state in `App.tsx`.

The new shell should become the primary container for:

- quest authoring
- apprentice progression
- mentor and steward tools
- guild review surfaces
- future quest commons workflows

The existing world-shell guild tab can remain as a lightweight summary or
shortcut back into the dedicated guild workspace, but it should stop being the
primary place where serious guild work happens.

This slice does not require a full guild redesign on day one. It should first
establish the dedicated shell and move the current guild surface into a better
container, creating room for the later guided-composer work.

## Files Affected

- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/components/GuildShell.tsx`
- `worldweaver_engine/client/src/components/GuildBoard.tsx`
- `worldweaver_engine/client/src/components/GuildQuestPanel.tsx`
- `worldweaver_engine/client/src/components/WorldInfoPane.tsx`
- `worldweaver_engine/client/src/styles.css`

## Acceptance Criteria

- [x] Guild access mode can load a dedicated guild shell instead of routing serious guild work through `WorldInfoPane`
- [x] The dedicated guild shell becomes the main place for quest authoring and mentor/steward workflows
- [x] The world shell can still expose lightweight guild summary or shortcut access without duplicating the full guild workspace
- [x] Existing guild board behavior continues to work after being moved into the new container
