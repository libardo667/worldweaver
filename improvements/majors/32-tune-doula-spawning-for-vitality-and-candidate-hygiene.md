# Tune doula spawning for vitality and candidate hygiene

> ⏳ **REVISIT (parked 2026-06-08)** — not active, not dead. Wake-up trigger in [`improvements/REVISIT-LATER.md`](../REVISIT-LATER.md).

## Problem

The doula loop is live, but its current decision surface is still too noisy and
too random for the new Postgres-backed runtime.

Current issues:

- spawn decisions still lean heavily on probabilistic gating in
  `ww_agent/src/loops/doula.py` instead of a more legible vitality model
- candidate hygiene is leaky: place-like entities such as neighborhoods can still
  surface as resident candidates before being filtered or voted down
- the doula mainly asks "is this untethered name near a tethered agent?" instead
  of "does this neighborhood or social surface actually need another resident?"
- neighborhood liveliness is not treated as an explicit target, so doula activity
  can feel random, sparse, or bunched
- skip/spawn reasons are not rich enough for operators to tell whether the doula
  is being cautious, confused, or starved of useful signals

This matters more now because the infrastructure ceiling has moved. Postgres and
the thinner narrative stack mean the simulation can support more activity. The
next bottleneck is no longer "can writes survive?" but "is the doula making good
population decisions?"

## Proposed Solution

Refactor doula spawning around structured neighborhood vitality and stronger
candidate hygiene, while keeping player-consent protections intact.

### Phase 1 - Candidate hygiene and explainable skip reasons

Fix the embarrassing failure mode first: place-like entities should stop showing
up as plausible resident candidates, and every skipped candidate should produce
an inspectable reason.

Changes in this phase:

- strengthen pre-spawn static/entity filtering in `ww_agent/src/loops/doula.py`
- use city-pack place names, known world nodes, and active-scene checks more
  aggressively before a candidate ever reaches poll/spawn logic
- add explicit skip reasons such as:
  - `static_place`
  - `already_active`
  - `player_without_consent`
  - `not_near_tethered_agent`
  - `cooldown`
  - `daily_limit`
- make those reasons visible in logs or a lightweight runtime artifact

This phase should reduce nonsense candidate lists before changing spawn volume.

### Phase 2 - Replace loose randomness with scored spawn readiness

Keep a rate limit and a small stochastic element, but make the core decision a
weighted score instead of "candidate exists + random roll."

Candidate readiness should consider:

- tether proximity
- local public activity scarcity
- social isolation thresholds
- recent neighborhood vitality
- graph or roster gaps
- prior skip / cooldown state

Randomness should become a tie-breaker, not the main gate.

The key design constraint: score components must be inspectable. This should not
be a black-box confidence number with no readable decomposition.

### Phase 3 - Add neighborhood vitality targets

Give the doula an explicit concept of local liveliness so it can preferentially
seed residents where the world is thin rather than where narrative evidence
happened to be noticed once.

Examples of vitality signals:

- unique active speakers in a neighborhood over a rolling window
- recent movement in/out
- number of tethered residents currently nearby
- ratio of world events to present characters
- whether a place repeatedly hosts players but lacks stable local residents

This does not need to become a heavy simulation sub-engine. It just needs to
turn "the world feels sparse here" into something machine-checkable.

The first version should stay neighborhood-level rather than trying to infer a
whole-city sociological model.

### Phase 4 - Improve spawn targeting

When the doula does decide to create a resident, the chosen entry location should
be tied to the neighborhood that justified the spawn, not a loosely random place.

Spawn targeting should prefer:

- neighborhoods below vitality target
- places with repeated player attention but weak resident presence
- social surfaces where existing residents are sparse or absent

This phase is where the system should start feeling less random and more
purposeful to players.

### Phase 5 - Add operator-facing diagnostics

Expose enough signal that an operator can understand the doula without reading
raw logs for an hour.

Useful outputs:

- candidate score breakdown
- neighborhood vitality snapshot
- explicit skip reason
- explicit spawn reason
- cooldown / rate-limit state

These can live in logs first and in a lightweight debug endpoint or runtime
artifact if needed.

## Suggested implementation sequence

This major should be landed as a few narrow, testable slices rather than one
large doula rewrite.

### Slice A - Candidate hygiene first

Goal: stop obvious static/place candidates and make skip reasons inspectable.

Likely changes:

- tighten `_classify()` and `_is_known_place()` in `ww_agent/src/loops/doula.py`
- add structured skip-reason logging
- add tests or deterministic fixtures for place/person edge cases where possible

Expected commit shape:

- `fix: harden doula candidate hygiene for static entities`

### Slice B - Spawn scoring without vitality targets yet

Goal: replace the current direct probability gate with a readable spawn-readiness
score built from existing local signals.

Likely changes:

- add a candidate score object / helper in `ww_agent/src/loops/doula.py`
- keep existing rate limits and consent rules unchanged
- preserve a small final random tie-breaker only after minimum score threshold

Expected commit shape:

- `refactor: score doula spawn readiness before random gating`

### Slice C - Neighborhood vitality substrate

Goal: add the minimal backend/world signals the doula needs to know which places
are socially thin versus already lively.

Likely changes:

- add lightweight neighborhood vitality query support in
  `worldweaver_engine/src/api/game/world.py`
  or a helper in `worldweaver_engine/src/services/world_memory.py`
- teach `ww_agent/src/world/client.py` to fetch that view
- thread vitality data into doula scoring

Expected commit shape:

- `feat: add neighborhood vitality signals for doula targeting`

### Slice D - Targeted spawning and operator diagnostics

Goal: make chosen spawn locations reflect the vitality reason, and expose enough
debug data to tune behavior live.

Likely changes:

- improve entry-location selection in `ww_agent/src/loops/doula.py`
- add candidate score breakdown and spawn reason logging
- optionally add a lightweight debug endpoint or runtime artifact

Expected commit shape:

- `feat: target doula spawns by neighborhood vitality`

## Non-goals for the first pass

To keep this major tractable, the first implementation should not try to solve
all future doula ambitions at once.

Out of scope for the first pass:

- player-shadow identity synthesis changes
- federation-wide cross-city doula reasoning
- complex social network modeling
- heavy review UI for human stewards
- full place/person/institution ontology redesign beyond what doula hygiene needs

## Files Affected

- `ww_agent/src/loops/doula.py`
- `ww_agent/src/world/client.py`
- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/src/services/world_memory.py`
- `improvements/NL_GRANT_PACK.md`
- `improvements/PRODUCT_PACK.md`

## Acceptance Criteria

- [ ] Doula candidate lists no longer routinely include obvious static geography such as neighborhoods or landmarks
- [ ] Spawn decisions produce a structured reason that mentions the main contributing signals
- [ ] Neighborhoods with repeated player presence but weak resident activity are preferentially targeted over already lively areas
- [ ] The doula can explain a "no spawn" cycle with concrete skip reasons instead of only silent non-action
- [ ] Daily rate limits and consent protections still hold
- [ ] Operators can inspect neighborhood vitality and candidate scoring without reading only free-form log prose

## Risks & Rollback

- Overcorrecting away from randomness could make spawning feel mechanical or overfitted.
  Mitigate by keeping a small stochastic tie-breaker after the main score.
- Vitality metrics can become another hidden control layer if they are too clever.
  Keep the first version simple, inspectable, and grounded in observable runtime data.
- Stronger candidate hygiene can suppress legitimate novel people if the place/person
  classifier becomes too conservative. Mitigate with explicit debug reasons and a
  reversible cooldown instead of permanent sealing on first sight.
- Rollback path: keep the current probabilistic path behind a feature flag or
  fallback branch until the vitality-driven path proves stable in live shards.
