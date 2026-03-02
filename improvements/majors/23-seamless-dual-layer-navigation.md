# Seamless Dual-Layer Navigation (Physical + Semantic)

## Problem

The current system has a hard divide between "spatial movement" (`DIRECTIONS` in `spatial_navigator.py`) and "storylet progression" (`pick_storylet`). Physics and Narrative are disconnected. `VISION.md` calls for a "dual-layer world" where "Physical space determines where you are; Semantic space determines what happens there." Currently, you move on a grid, and the grid cell determines the pool of eligible storylets.

## Proposed Solution

1.  **Semantic Coordinates**: Give every storylet a "semantic coordinate" (its embedding) AND a physical coordinate (grid X,Y).
2.  **Movement Warps Meaning**: As the player moves through physical space, their physical distance to storylets should act as a *modifier* to the semantic probability, not a binary filter.
3.  **Unbound Movement**: Allow "moving toward a concept" via freeform action, which shifts the player's physical coordinates toward the nearest cluster of storylets matching that concept.
4.  **Integrated Navigation API**: The `/spatial/navigation` endpoint should return both "Directions you can walk" AND "Leads you could follow" (semantic neighbors).

## Files Affected

- `src/services/spatial_navigator.py`: Rewrite navigation logic to be a weighted sum of physical distance + semantic proximity.
- `src/services/semantic_selector.py`: Incorporate 2D distance penalties into the scoring function.
- `src/api/game.py`: Unify spatial and semantic endpoints.
- `src/models/schemas.py`: Update navigation response to show combined results.

## Acceptance Criteria

- [ ] Walking North doesn't just show one storylet; it shows a ranked field of storylets that are "mostly North" but also "semantically relevant."
- [ ] High semantic relevance can "pull" a storylet from a neighboring grid cell even if it's not at the current coordinate.
- [ ] Player can type "I'm looking for the blacksmith" (semantic goal) and the system provides physical directions ("The sound of hammers rings from the East").

## Risks & Rollback

If navigation becomes too fluid, players may get lost or skip crucial world geography. Rollback by increasing the weight of physical distance in the selection cost function.
