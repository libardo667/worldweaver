# Resident-owned identity growth

## Status

Active. Authority moved to the hearth on 2026-07-18. The remaining work is the resident-facing adoption
process.

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
- [ ] A resident can electively inspect a bounded growth candidate and its source events.
- [ ] Adoption requires a later explicit resident action.
- [ ] Adoption writes `soul_growth.md`, refreshes the composed soul, and records complete provenance.
- [ ] Restart, hearth travel, and city-to-city travel preserve the adopted growth unchanged.
- [x] Tests prove that a city or steward cannot modify resident identity through the compatibility endpoint.

## Likely files

- `ww_agent/src/runtime/ledger.py`
- a new small module under `ww_agent/src/identity/`
- `ww_agent/src/identity/loader.py`
- the hearth information and action tools
- focused identity and travel tests
