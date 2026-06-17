> **STATUS: CLOSED 2026-06-11 — superseded by Major 68 (guild removal).** This is a
> guild-era item; Major 68 extracts and removes all guild references and affordances, so the
> surface this item authors for no longer exists. Closed under 68 per the 2026-06-11 direction
> review (§2). Archived (not deleted) for record; reinstate only if the guild is ever revived.

# Add quest scattering and evidence rubric to the authoring flow

## Problem

The current shard behavior shows signs of local echo chambers: repeated motifs,
shared vocabulary loops, and strong ambient convergence inside the same
neighborhood and conversational basin.

Quest creation is one of the clearest levers available for countering that
pattern, but the current UI does not explicitly help authors create quests
that:

- pull residents into new places
- connect them with different people
- require grounded observation
- generate checkable evidence

Without that rubric, a quest author can accidentally write a task that sounds
interesting but merely reinforces the shard's current local style.

## Proposed Solution

Add a visible quest quality rubric directly into the quest authoring flow.

The composer should surface prompts such as:

- What new person, neighborhood, or institution does this expose them to?
- What concrete observation or action would count as success?
- What evidence would distinguish completion from aesthetic performance?
- Is this quest grounded enough to resist the current local echo chamber?

The rubric should be advisory, not bureaucratic. Its purpose is to shape better
quest design and better social feedback opportunities, not to create a review
tax.

## Files Affected

- `worldweaver_engine/client/src/components/GuildBoard.tsx`
- `worldweaver_engine/client/src/components/GuildQuestPanel.tsx`
- `worldweaver_engine/client/src/styles.css`

## Acceptance Criteria

- [x] Quest authoring surfaces explicitly ask for diversity/scattering pressure and success evidence
- [x] The UI nudges authors toward grounded, checkable quests rather than purely aesthetic or atmospheric ones
- [x] Contributors can understand why a quest helps break local echo loops instead of only seeing abstract guild vocabulary
- [x] The rubric improves quest quality without blocking experienced authors behind excessive validation
