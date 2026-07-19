# Finish the first private consequence-driven game town

## Status

The first playable town is Alderbank, a small fictional river settlement with a schematic map. The game
rules are opt-in per shard and do not change ordinary commons cities.

The engine now provides software-enforced movement, local speech and marks, durable objects, material
recipes, making, giving, accepted exchange, reclaimable placement, bounded object stoops, and non-trapping
room access. Humans and residents call the same domain services. The public client exposes these actions at
the current place, including giving, exchange, door controls, and known city travel. Four game-native
resident homes exist, and bounded resident and human play has exercised parts of the town, including an
actual stoop exchange.

The first public human play found and fixed a real shared-contract bug: an active stoop object was also
listed as a loose object at the same place. Active stoop entries now suppress that second view, and the
ordinary object surface only offers pickup when the server says the caller may reclaim the object. Human
participants can now read and leave the same local, expiring physical marks as residents.

This is a playable foundation, not yet a completed playtest. Several-session recovery, a complete four-
resident run, and a demonstrated longer consequence chain remain open.

## Goal

Make a private game where choices change later possibilities through ordinary software state. The language
model decides what a resident attempts and how they express it; it does not invent whether an object moved,
a recipe succeeded, a door opened, or an exchange completed.

## Build next

1. Close any remaining human/resident action parity gaps in the public client.
2. Run Alderbank across several stopped and restarted private sessions with one human and the four new
   residents.
3. Exercise making, placement, stoops, access invitations, giving, exchange, travel home, and return.
4. Add one understandable consequence chain where an earlier structured choice changes a later available
   action. Keep it constructive and reversible.
5. Record structured receipts and recovery results without collecting private resident prose, prompts,
   memories, letters, or hearth activity.
6. Fix failures found by play, then write a short findings report covering usability, cost, recovery,
   consequence integrity, and conversation health.
7. Decide later whether this remains a private game, becomes a separate public product, or contributes only
   engine features to the commons.

## Rules

- Game rules are declared and versioned by the shard.
- Humans and residents obey the same world transactions.
- Objects have stable identity, provenance, custody or exact placement, and restart-safe state.
- Operations are atomic and idempotent where interruption can occur.
- A resident can refuse, remain quiet, leave for their hearth, and return.
- No survival scarcity, deprivation, injury, death, imprisonment, forced loss, resident experience points,
  approval optimization, or engagement rewards in this phase.
- Private resident data is not game analytics.
- A public release requires a separate safety, moderation, privacy, and operations decision.

## Acceptance criteria

- [x] A shard declares a versioned game ruleset without changing commons or hearth defaults.
- [x] Alderbank builds, validates, launches, and presents itself as a game in plain language.
- [x] Durable objects, making, giving, accepted exchange, placement, stoops, and access are enforced by
  software transactions rather than prose.
- [x] The ordinary human surface is place-centered and excludes resident-private telemetry.
- [ ] Every supported action has matching human and resident contracts and clear failure receipts.
- [ ] Four game-native residents can enter, act or decline, withdraw home, and return in one recoverable run.
- [ ] Several private sessions survive full stop and restart without lost or duplicated state.
- [ ] One earlier structured choice changes a later available action in a way a player can understand.
- [ ] Analytics contain structured world facts only and no private resident prose or hearth data.
- [ ] A concise private-play report records the remaining bugs and the public-release decision remains open.
