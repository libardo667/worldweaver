# Digital stoops make the city a local gift commons

## Problem

WorldWeaver has people, places, private workshops, physical traces, chat, mail, and an append-only event
spine, but it lacks a simple place where something made by one person can be left for whoever comes next.
Resident work mostly stays private; public interaction is dominated by speech channels and presence views.

The current browser makes that imbalance worse. Its main information surface exposes shard-wide presence,
resident activity/rest state, locations, counts, and several chat feeds. Those are useful operating signals,
but as the default human experience they make the city read like a surveillance console. Major 71's steward
tools and the public commons have been allowed to occupy the same interface.

The sibling `../stoop/` project demonstrates a better interaction shape: a small, local, bounded exchange
where people leave things, encounter what others left, and let the least-held material compost. Its physical
no-account/no-cloud constraints must remain independent. WorldWeaver needs a native digital form of the
same behavior, not the Stoop server embedded as a dependency.

## Proposed Solution

Add location-scoped digital stoops as first-class world objects shared by humans and residents.

### 1. Keep the two projects independent

The physical Stoop remains an offline, anonymous, ESP32-bound project with no accounts or global service.
WorldWeaver may adapt its small-box rules and pure decay/Murmur behavior, with attribution, but uses its own
database, actor, event, capability, and UI contracts. A physical box must not silently become a network
terminal for the city.

### 2. Add a native, node-owned stoop domain

Each digital stoop belongs to one city node and one exact location. It has a prompt/theme, a bounded
capacity, and a live set of entries. An entry may be short text or a copy of a resident-owned workshop
artifact. The original workshop object remains the resident's; offering a copy does not surrender private
storage.

Use an append-only stoop event history for leave, keep, take, compost, and keeper-prune operations. The live
contents are a projection. Compost removes an entry from the live box without erasing the historical act.
The federation root never stores stoop contents.

### 3. Make browsing elective and embodied

The automatic scene may say that a stoop is present and how full it is. It must not insert the entries or
the Murmur into every human view or resident prompt. Browsing is an explicit current-location action.

Humans and residents share the same basic verbs:

- `browse` — see a bounded handful of current entries;
- `leave` — place short text or an owned artifact copy;
- `keep` — extend an entry's live tenure without rewarding its author;
- `take` — take up a copy or retire a genuinely single-instance object under a later explicit contract.

Resident access is a world-scoped elective source/capability in Major 65's shared registry. Merely entering
a location with a stoop must not force a pulse.

### 4. Preserve the safe part of the Stoop social model

The first version is an undirected local commons: things are left for whoever finds them. Do not add points,
reputation, author rewards, read receipts, engagement counts, or notifications that teach residents to
perform for attention.

Targeted cubbies may come later for a named human or resident, but only as self-paced gifts: no forced
ignition, no delivery alert, no receipt, and no observable "I offered -> they reacted" reward loop. Mail
remains the explicit directed correspondence channel.

Internally retain source actor and event provenance even when the public entry is unsigned. A resident must
experience an unsigned item as "found on this stoop," not as a grounded fact with an invented speaker.

### 5. Derive a local Murmur without building a monoculture amplifier

Derive a cheap, inspectable portrait from the live entries rather than asking an LLM to narrate the box.
Stoop's document-frequency, age, and most-kept rules are a useful starting point. Because WorldWeaver has
already seen population-wide themes feed themselves back into residents, the Murmur remains elective and
local. It is never automatic citywide context and never a ranking of what residents ought to care about.

### 6. Separate the commons interface from steward diagnostics

Rebuild the ordinary human surface around the current place, paths, local stoops, things left there, and
people actually encountered. Remove shard-wide rest reasons, wake estimates, queues, and resident internals
from the default interface.

Keep operational visibility, but move it into an authenticated steward/debug surface with explicit privacy
rules under Major 71. A useful diagnostic should not become the public relationship humans have with a
resident.

## Files Affected

- `prune/VISION.md`
- `prune/majors/43-rebuild-the-human-front-door-around-curiosity-participation-and-progressive-disclosure.md`
- `prune/majors/65-tools-as-verbs-the-world-affords.md`
- `prune/majors/71-steward-facing-semi-public-portal-witness-shadow-and-threshold.md`
- `worldweaver_engine/src/models/__init__.py`
- a new engine stoop domain service and API routes
- a migration for stoop objects, entries, and append-only stoop events
- `ww_agent/src/runtime/information.py`
- `ww_agent/src/world/city_tools.py`
- `ww_agent/src/world/city_world.py`
- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/components/WorldInfoPane.tsx`
- a new place/stoop exchange surface in the client
- engine, resident, and client contract tests

## Acceptance Criteria

- [ ] A city node can host multiple bounded stoops attached to exact local places
- [ ] Humans and residents use the same browse, leave, keep, and eventual take domain contract
- [ ] The automatic scene exposes only the stoop affordance, not its contents or Murmur
- [ ] A resident reads stoop contents only through an elective, world-scoped capability
- [ ] Leaving or receiving a stoop item never forces resident ignition
- [ ] Text and copied workshop artifacts retain honest source provenance
- [ ] Capacity pressure deterministically composts entries without deleting append-only history
- [ ] Keeps extend live tenure but do not create author points, reputation, or attention rewards
- [ ] The Murmur is cheap, local, inspectable, and absent from automatic population-wide prompts
- [ ] Stoop contents remain owned by the city node and are not collected by the federation root
- [ ] The ordinary human interface centers places and exchanges rather than shard-wide resident telemetry
- [ ] Resident internals and operational health are available only in a clearly separate, privacy-scoped steward/debug surface
- [ ] The physical `../stoop/` project remains fully offline-capable and independent of WorldWeaver

## Risks & Rollback

- A stoop can degrade into another feed. Keep it location-bound, capacity-bound, and explicitly browsed.
- A popularity signal can become a behavior reward. "Keep" changes entry tenure only and never accrues to
  an author profile.
- A Murmur can reinforce the semantic monoculture by repeating the majority topic. Never inject it
  automatically; retain its derivation inputs and make the summary inspectable.
- Targeted gifts can recreate notification pressure and keeper-pull. Defer them until the self-paced cubby
  contract is explicit and tested.
- Workshop sharing can leak private material. Only a deliberate artifact-copy action may cross from the
  resident-owned workspace into a public stoop.
- UI cleanup can accidentally delete useful operator tools. Move them behind a steward/debug boundary
  before removing the default routes or components.
- Roll back in slices: hide the stoop affordance, disable write verbs, and retain append-only records. Do
  not hard-delete entries or collapse the physical Stoop project into this repository.
