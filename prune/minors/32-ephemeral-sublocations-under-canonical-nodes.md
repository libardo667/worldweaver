# Sublocations under canonical map nodes

> ▶ **READY (live resident evidence 2026-07-17).** Major 36's map, navigation, and occupancy work remains
> the owning dependency. Major 63 closed without needing finer sublocations for speech privacy, but a live
> resident has now independently attempted a reasonable within-neighborhood move that the flat graph could
> not represent.

## Problem

Residents and players sometimes refer to plausible within-place destinations that
are not part of the canonical city-pack graph:

- `back booth`
- `bench by the laundromat`
- `their stall`
- `alley behind the Arms`
- `the duplex near Arbor Lodge Park`

Today these phrases are just bad movement targets. They fail graph validation and
quietly disappear. That keeps the canonical map clean, but it also throws away a
useful layer of lived local texture.

### Live evidence: Jarosław Nowak, 2026-07-17

During an unsteered Portland run, Jarosław used an ordinary reactive pulse to attempt a `move` from the
canonical `Arbor Lodge` node to `the duplex near Arbor Lodge Park`. The city rejected it because its route
API accepts only exact canonical graph destinations. This was not a request to visit another neighborhood;
it was a reasonable attempt to locate a home-scale place inside the neighborhood where he had been seeded.

That case corrects one assumption in the original minor: not every sublocation is disposable scene texture.
Some are temporary (`back booth tonight`), while others may be durable personal or steward-defined places
(`their duplex`, `the tattoo room`, `the shop's back room`). The parent graph node remains canonical in both
cases; the sublocation needs its own identity and declared lifetime rather than being inferred from prose on
every move.

## Goal

Allow scene-rich, non-canonical place refinements to exist without polluting the
durable city graph.

The intended model is:

- canonical graph nodes remain the durable navigable map truth
- sublocations can exist underneath a canonical parent location
- each sublocation declares whether it is ephemeral or durable
- ephemeral sublocations remain temporary, local, and removable

This is not a replacement for graph-grounded movement. It is a secondary layer
for scene texture once canonical movement has already landed somewhere real.

This minor now also carries a second job:

- giving scene synthesis somewhere concrete to land
- making local places feel more lived-in and less samey
- providing temporary structure for ambient presence and lightweight occupancy as
  formalized in
  [`33-lightweight-ambient-presence-for-scene-synthesis.md`](prune/minors/33-lightweight-ambient-presence-for-scene-synthesis.md)

## Proposed Model

Treat non-canonical destinations as candidate **subjective sublocations** when
they clearly describe a place *within* the current canonical location. A candidate
must resolve to an existing sublocation or pass a bounded creation rule; arbitrary
prose must not silently become durable map truth.

Each sublocation should carry:

- stable `sublocation_id`
- canonical `parent_location_id`
- `label`
- `persistence`: `ephemeral` or `durable`
- `created_by_session`
- `created_at`
- `last_active_at`
- `ttl_seconds` when ephemeral
- optional lightweight occupancy
- optional ambient-presence descriptors

Rules:

- ephemeral sublocations must always belong to a canonical parent node
- they must never automatically become durable map nodes
- they should expire when inactive for long enough
- durable sublocations require an explicit city-pack, steward, resident-home, or promotion source
- repeated/shared use can later inform promotion decisions, but promotion is a
  separate explicit process

## Scope

In scope:

- scene-local sublocation creation
- durable personal or steward-defined sublocations under a canonical parent
- TTL cleanup
- attaching residents/players to sublocations under a canonical parent
- UI surfaces that can show "someone is at the back booth of X"
- optional ambient or background presences attached to those sublocations

Out of scope:

- automatic promotion into the city-pack graph
- freeform cross-city travel targets
- replacing canonical route planning with fuzzy prose locations

## Interaction With Movement

Canonical movement must still resolve to a real graph node first.

Suggested flow:

1. move to canonical node
2. optionally enter a sublocation under that node
3. expire it when unused if its declared persistence is ephemeral

This prevents bogus movement phrases from becoming graph pollution while still
letting the world express richer local detail.

## Why This Is Worth Keeping Open

This gives the map and scene system a middle layer:

- richer than only canonical city-pack nodes
- safer than letting every phrase become a durable graph entity

It also aligns well with the longer-term resident/world fractal direction:
temporary local structure can exist, be observed, and then either fade or earn
promotion later.

It also creates a concrete target for the reclaimed scene-synthesis layer in
Major 10: generated local structure should not have to jump straight from prose
to canonical graph mutation.

It is also the natural landing zone for the ambient-presence layer: if a place
needs a queue, prep spillover, commuters under an awning, or a few regulars at
the edge of the room, that should attach here rather than becoming a fake
durable actor or polluting the canonical map.

## Acceptance Criteria

- [ ] Non-canonical within-place destinations can be represented without entering the durable map graph
- [ ] Every sublocation has a stable ID and always attaches to a canonical parent location
- [ ] Durable personal/steward sublocations and ephemeral scene sublocations have explicit, different lifetimes
- [ ] Inactive ephemeral sublocations expire automatically
- [ ] The canonical navigation graph remains clean and queryable
- [ ] This layer is treated as optional scene texture, not as a substitute for graph-grounded movement
- [ ] Scene synthesis and lightweight ambient presence can attach to sublocations without forcing durable graph changes
