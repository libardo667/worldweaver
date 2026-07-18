# Rebuild the human front door around curiosity, participation, and progressive disclosure

## Problem

The frontend is not failing because it lacks visual identity. It is failing at
the threshold.

Right now the first-run experience asks a new human to absorb too much
institutional meaning before they have enough trust or curiosity to continue.
The front door is too concept-dense, too ceremonious, and too emotionally
uniform.

The heaviest problem points are:

- [`worldweaver_engine/client/src/components/EntryScreen.tsx`](worldweaver_engine/client/src/components/EntryScreen.tsx)
- [`worldweaver_engine/client/src/components/OnboardingModal.tsx`](worldweaver_engine/client/src/components/OnboardingModal.tsx)
- [`worldweaver_engine/client/src/components/SettingsDrawer.tsx`](worldweaver_engine/client/src/components/SettingsDrawer.tsx)
- [`worldweaver_engine/client/src/App.tsx`](worldweaver_engine/client/src/App.tsx)

Today the frontend front-loads:

- shard choice
- threshold doctrine
- auth
- reset password
- participation mode
- mentor/steward role vocabulary
- location choice
- continuity/tether implications
- model/economic settings

That creates a strong but intimidating threshold. Many users experience the app
less as "a world already in progress" and more as "a serious terminal rite with
unknown commitments."

This is now a product problem, not just a component-complexity problem.

### Direction correction — 2026-07-17

The problem continues after the threshold. The current world mode centers maps of occupancy, shard-wide
presence/rest telemetry, and multiple feeds. Useful operator data has become the default way a human looks
at residents. Major 125 now supplies the missing positive interaction model: enter a place, encounter what
is there, and participate through local digital stoops and other world affordances. Steward diagnostics are
a separate privacy-scoped mode under Major 71.

### Situated-interface checkpoint — 2026-07-18

The ordinary client now has a real `Here` panel for the current place, nearby people and objects, making,
stoops, exchange, and room access. The freeform action box, paid narrator call, personal model-key controls,
model picker, and expired observer paywall have been removed. The remaining text stream is read-only history,
and it has been narrowed so the place/map side has more room.

The intended default is now clearer: the human surface should look like a place a person can move through,
not a terminal for writing commands and watching logs. Show the current place, a small truthful map, and
buttons for actions that are actually available here. Keep the activity log as an optional history or
inspection view. A polished text-forward view may remain useful for accessibility and experienced users,
but it should be another view over the same typed commands, not a second gameplay system.

## Proposed Solution

Reframe the frontend around a lighter first-run threshold and stronger
progressive disclosure.

The governing rule for the first-run flow should be:

1. what is this place?
2. can i safely enter?
3. how much of myself do i want to bring in right now?

The frontend should stop asking advanced guild, continuity, stewardship, and
economic questions at the public threshold. Those concepts still belong in the
product, but they should arrive later, after the user has entered and cared.

This major should establish three frontend modes with different weights:

- threshold mode
  - brief, calm, atmospheric, and trust-building
- world mode
  - the main lived-in interface for moving, encountering local people and things, browsing stoops, and
    participating without shard-wide surveillance
- guild/admin mode
  - clearer, calmer, more structured surfaces for mentor, steward, and review work

This major is implemented through the following subordinate slices:

1. simplify first-run entry to `look around` vs `join the world`
2. remove mentor-board presentation from public onboarding
3. split `EntryScreen` into smaller flow components
4. split `SettingsDrawer` into clearer account and continuity surfaces
5. decompose `App.tsx` into mode-specific hooks and surfaces
6. make place/map/actions the ordinary default and make the activity log optional

This major does not aim to flatten WorldWeaver into a generic SaaS app. It
keeps the world’s tone and soul, but changes the sequencing so curiosity wins
before doctrine arrives.

## Files Affected

- `prune/FRONTEND_PROBLEMS.md`
- `prune/FRONTEND_OVERHAUL.md`
- `prune/minors/34-simplify-first-run-entry-into-look-around-vs-join.md`
- `prune/minors/35-remove-mentor-board-from-public-onboarding.md`
- `prune/minors/36-split-entry-screen-into-flow-components.md`
- `prune/minors/37-split-settings-into-account-narration-and-continuity-surfaces.md` (rebaseline or archive;
  the narration/model surface it named has been removed)
- `prune/minors/38-decompose-app-shell-into-mode-specific-hooks-and-surfaces.md`
- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/components/EntryScreen.tsx`
- `worldweaver_engine/client/src/components/OnboardingModal.tsx`
- `worldweaver_engine/client/src/components/SettingsDrawer.tsx`

## Acceptance Criteria

- [ ] The first-run public threshold presents only two primary actions: `look around` and `join the world`
- [ ] A new user can enter observer mode without being forced through guild-role language, auth, or continuity doctrine
- [ ] A new participating user can create or enter an identity without seeing mentor-board or steward-specific tools at the threshold
- [ ] Mentor/steward capabilities remain available, but are surfaced after auth and role resolution instead of as public entrance options
- [ ] `EntryScreen.tsx` is no longer a single component owning shard selection, threshold copy, auth, password reset, participation mode, mentor gating, and location selection all at once
- [x] `SettingsDrawer.tsx` no longer asks a human to configure a narrator model or personal model key
- [ ] `SettingsDrawer.tsx` cleanly separates the remaining account and continuity/tether concepts
- [ ] `App.tsx` is measurably less responsible for unrelated onboarding, guild, observer, chat, and settings state at the same time
- [ ] The front door still feels like WorldWeaver, but no longer feels like a terminal-ritual gatekeeping ceremony
- [ ] The default world mode does not expose shard-wide resident internals, rest reasons, wake estimates, or operator queues
- [ ] Places, locally encountered people, and local exchange affordances are more prominent than population telemetry and broadcast feeds
- [ ] The ordinary default shows available actions as concrete controls and gives the local map enough space
      to orient and move without learning a command syntax
- [ ] The activity log can be hidden or opened without changing world behavior or creating a second action path

## Risks & Rollback

The main risk is overcorrecting and flattening the project’s distinct tone into
a generic, low-character product shell.

Secondary risks:

- guild/steward concepts become too hidden to discover later
- observer and participant paths drift apart in confusing ways
- the frontend refactor creates regressions in auth/bootstrap flow

Rollback path:

- keep the old threshold language and role surfaces behind feature flags while
  the new flow lands
- preserve existing auth/bootstrap helpers during the component split
- stage this major through the linked minors so the old and new flows can be
  compared safely
