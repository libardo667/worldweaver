# Finish sublocations under canonical places

## Status

Ephemeral sublocations are implemented. A resident can enter or narrowly create a plausible place within
their current canonical location, such as a back room or nearby bench. Each child has a stable parent-scoped
ID and expiry. It never becomes a route in the canonical city graph. Exact sublocation names already scope
speech, traces, events, and presence.

## Remaining problem

Some small places are durable rather than temporary: a home room, shop stall, studio, or steward-authored
back room. There is no explicit durable child-place contract or promotion path yet. The public client also
needs a clear way to show that a person is inside a child place without treating it as another neighborhood.

## Build next

1. Add an explicit `durable` child-place type with a named source: city pack, resident hearth/home, or
   steward publication.
2. Keep automatic resident prose creation ephemeral. Promotion to durable always requires a separate,
   explicit action.
3. Add public-client labels and movement controls that preserve the canonical parent context.
4. Attach the environmental activity from Minor 33 to either a canonical place or a child place.
5. Add cleanup and migration tests proving expiry never deletes durable children or pollutes route data.

## Acceptance criteria

- [x] Ephemeral child places have stable IDs, canonical parents, bounded creation, and expiry.
- [x] Canonical navigation remains free of child-place routes.
- [x] Speech, traces, events, and presence can use an exact child-place scope.
- [ ] Durable child places have an explicit source and never expire through ephemeral cleanup.
- [ ] Promotion from ephemeral to durable is deliberate and recorded.
- [ ] The public client can enter, leave, and display child places without confusing them with neighborhoods.
- [ ] Deterministic environmental activity can attach to either level.
