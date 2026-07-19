# Resident-owned identity growth

## Completed (2026-07-18)

Residents can now inspect and adopt their own identity proposals at their hearth. The `growth` information
source returns one accepted `soul_edit` at a time, using the resident's exact words and showing the source
pulse and proposal event IDs. It does not include goal or reverie updates, dropped proposals, or another
resident's material.

Adoption is a separate `do` action addressed to that exact proposal. It works only after the proposal's
record has crossed the private information boundary and only while the resident is in a live hearth.
Cities do not expose the source or action. A successful adoption appends the exact wording to
`identity/soul_growth.md`, refreshes the composed and in-memory soul, and records a `growth_adopted` event
plus durable metadata linking the proposal, inspection, adoption, actor, and source events. Retrying the
same adoption does not add a second event or duplicate text. Startup also repairs an interrupted identity
file write from the already-recorded adoption event.

Focused tests cover filtering, inspection-before-action, city refusal, provenance, restart, live drive
refresh, hearth travel, and city-to-city travel.

## Problem

A resident can propose a change to their own identity. Accepted proposals are recorded as
`self_delta_staged` events in the resident's private ledger.

The old implementation sent those proposals to the current city. The city embedded them, compared them
with other residents, rejected some with text patterns, and automatically wrote selected lines into the
resident's identity. That made a host city the judge of who a visiting resident became.

That path is now disabled. `identity/soul_growth.md` in the hearth is authoritative. Old city-stored growth
can migrate into an empty hearth once, but a city cannot replace existing hearth growth. New proposals stay
private. Nothing currently promotes them automatically.

## Build next

Add a small, hearth-local process with three separate steps:

1. Gather accepted self-edit proposals from the private ledger without sending their text to a city.
2. Let the resident inspect a bounded candidate with links to its source events and earlier related
   proposals.
3. Only after a later, explicit resident action, append the adopted line to `soul_growth.md` and record a
   `growth_adopted` event with the exact source IDs.

Repeated wording may help find a candidate, but it is not proof of growth. Do not automatically promote a
phrase because it recurs. Do not compare the resident with population themes. Do not use text filters to
ban social, emotional, or goal-related identity claims. A steward may inspect this machinery with the
resident's permission but is not the approval gate.

The first version should select one of the resident's own formulations. It should not ask another model to
rewrite the proposal. It also should not silently delete older adopted growth to meet a size cap; any later
compaction needs its own explicit, reversible decision.

## Acceptance criteria

- [x] The hearth, not a city database, is authoritative for mutable identity growth.
- [x] Existing city growth can migrate once without overriding an established hearth layer.
- [x] Current residents no longer transmit private self-edit proposals to cities.
- [x] The city no longer promotes, rejects, embeds, or population-compares identity proposals.
- [x] A resident can electively inspect a bounded growth candidate and its source events.
- [x] Adoption requires a later explicit resident action.
- [x] Adoption writes `soul_growth.md`, refreshes the composed soul, and records complete provenance.
- [x] Restart, hearth travel, and city-to-city travel preserve the adopted growth unchanged.
- [x] Tests prove that a city or steward cannot modify resident identity through the compatibility endpoint.

## Likely files

- `ww_agent/src/runtime/ledger.py`
- a new small module under `ww_agent/src/identity/`
- `ww_agent/src/identity/loader.py`
- the hearth information and action tools
- focused identity and travel tests
