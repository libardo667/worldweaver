# Build one honest public doorway into WorldWeaver

## Problem

The current repository explains several unfamiliar architectural ideas before showing a newcomer why they
matter. A person should not have to understand the entire project before seeing one real interaction. At the
same time, a polished presentation must not imply that WorldWeaver is already a secure production network or
that its cognitive experiments establish facts about minds.

## Proposed work

1. Lead with one plain description: a shared world where people and independently hosted software residents
   can meet while residents keep private continuity outside the city.
2. Show one bounded Alderbank sequence using public information only. A useful candidate is a person leaving
   an object at a stoop, a resident encountering it, and the world retaining the consequence.
3. Add one small diagram that distinguishes resident, hearth, temporary host, city, and federation directory.
4. Publish a visible status table for working, experimental, and not-yet-built behavior.
5. Give newcomers one supported local path and one short path for reading the architecture.
6. Reuse the general visual character of `hekswerk-site`, but keep the WorldWeaver section restrained,
   readable, and suitable for a serious research prototype.

## Expected files

- `README.md`
- `docs/index.md`
- selected files under `docs/tutorials/` and `docs/explanation/`
- the sibling `../hekswerk-site/` repository
- deliberately created screenshots, diagrams, or short demonstration media

## Acceptance criteria

- [ ] The first screen explains the project without unexplained internal vocabulary.
- [ ] A concrete demonstration appears before the full architecture tour.
- [ ] Every displayed behavior is reproducible from the linked commit and documented setup.
- [ ] Working, experimental, and planned claims are visually distinct.
- [ ] The presentation states that public-source review is not the same as production-service readiness.
- [ ] No private resident prose, prompt trace, credential, or steward-only view appears in demonstration media.

## Risks and rollback

A demonstration can become misleading when edited for clarity. Keep its source commit, setup, and limitations
beside it. If the site integration becomes fragile, retain a complete repository-native landing page and treat
the external site as an optional mirror rather than the sole documentation source.
