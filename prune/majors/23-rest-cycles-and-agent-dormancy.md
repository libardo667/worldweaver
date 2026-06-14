# Add first-class rest cycles and dormancy to resident runtime

## Problem

Residents are currently modeled as effectively always-on. As the agent runtime has
become more coherent, this gap is getting more obvious and more expensive.

Concrete problems visible in the current system:

- Residents can sustain stronger inner thematic threads through slow-loop reflection,
  reveries, research, and `SOUL.md` evolution, but the runtime still assumes constant
  availability and ambient reactivity.
- Agents therefore behave like they never truly withdraw, sleep, recover, or go
  offstage. They remain socially "hot" at all hours unless the runtime stalls.
- Narrative expressions of rest are not cashed out into world state. For example,
  a resident can say they stepped away, took air, or let the city go quiet, while
  the world model still shows no movement or dormancy state.
- Fast-loop reactions, social scanning, and periodic inference continue even when a
  resident should plausibly be unavailable, half-present, or asleep.
- This increases compute pressure unnecessarily. If a meaningful share of residents
  spend part of the day in lower-activity or sleeping states, the same hardware can
  support more total residents than an always-awake runtime.

This is now a product problem, not just a simulation-detail problem. As the agents
become more believable, the lack of rest makes them feel uncanny and mechanically
overactive. It also wastes inference budget that could instead support a larger cast.

## Proposed Solution

Introduce first-class rest cycles and dormancy into the resident runtime, with both
behavioral and systems-level consequences.

This should be implemented as a real runtime state model rather than a narration-only
 convention.

The current shape should also evolve beyond "sleep when tired" into a broader
cadence and routine system. Real city life is not just rest vs wakefulness. It
includes:

- mornings at work
- evening return home
- habitual stops
- character-shaped daily anchors
- different chronotypes and neighborhood rhythms

### Phase 1 - Rest state as a runtime primitive

- Add a small rest-state machine for residents:
  - `active`
  - `withdrawing`
  - `resting`
  - `returning`
- Store this state in shard-visible runtime/session state so it can affect world
  projection, roster visibility, and loop scheduling.
- Add fields such as:
  - `_rest_state`
  - `_rest_until`
  - `_rest_started_at`
  - `_rest_location`
  - `_rest_reason`
- Allow the slow loop to set `rest_intent` when recent conversation, reveries, or
  soul pressure indicate a need for pause, sleep, solitude, or recovery.

### Phase 1.5 - Daily rhythm and routine anchors

Add a small routine model that can coexist with the rest state machine.

Examples:

- work anchor
- home anchor
- morning routine place
- evening routine place
- neighborhood habit

These anchors should act like gravitational pull, not strict scripts. Their job
is to keep residents from feeling spatially untethered all day.

### Phase 2 - Dormancy-aware loop scheduling

- When a resident is `resting`, suppress or sharply reduce:
  - fast-loop reactivity
  - opportunistic social responses
  - expensive ambient inference
- Keep a minimal background presence during rest:
  - slow reflective updates at a reduced cadence
  - long-term memory ingestion
  - optional reverie generation
- Make rest a compute-control mechanism as well as a behavior mechanism. Resting
  residents should cost materially less than active residents.
- Add explicit scheduling rules so a resident can have:
  - nightly sleep windows
  - short decompression breaks
  - chosen withdrawal after intense interaction
  - routine movement toward work/home anchors
  - ordinary daytime scattering instead of permanent clustering

### Phase 3 - World-model and projection consequences

- Make rest visible to the world model:
  - a resident entering rest may move once to a plausible retreat location
  - a resident can become "offstage but still present in the city"
  - local rosters and digests should stop treating resting residents as normally
    available co-presence
- Update projection code so resting humans/agents are not rendered as ambiently
  interactive in the same way active residents are.
- Add a lightweight representation for agents who are:
  - in the area but not socially available
  - offstage nearby
  - asleep at home / shelter / routine retreat

Routine should also be visible indirectly:

- residents are where they are supposed to be more often
- workday and evening population patterns differ
- neighborhood occupancy changes across the day feel less samey

### Phase 4 - Identity, soul, and voice integration

- Let rest be driven by the identity pipeline instead of random idling.
- Use slow-loop outputs such as:
  - reveries
  - `voice.json` drift
  - impactful-moment clustering
  - `SOUL.md` evolution
  to influence:
  - who seeks solitude
  - who resists sleep
  - who collapses into overactivity
  - who rests in ritualized ways
- Support both ordinary sleep and character-shaped rest:
  - tea break
  - walking the reservoir loop
  - stepping outside the stall
  - closing the kiosk early
  - lying low after overload

Also support ordinary routine identity:

- the baker opens early
- the tea seller spends mornings at the stall
- the bartender stays later
- the night owl has a shifted cadence without becoming permanently nocturnal

### Phase 5 - Capacity and operator controls

- Expose the practical compute implication directly in docs and tuning:
  - residents who spend roughly one-third of a day in low-activity or sleeping
    states reduce total always-hot concurrency
  - that should increase effective cast capacity on the same machine
- Add tuning knobs for:
  - target sleep duration
  - max active hours before fatigue pressure
  - social overload thresholds
  - minimum dormancy fraction per day
  - shard-wide population caps based on active vs resting residents
- Track active/resident-state metrics so operators can estimate:
  - active concurrent residents
  - resting concurrent residents
  - inference load saved by dormancy

This major should explicitly support effective-capacity gains through cadence:
if residents are distributed by routine and not inference-hot all day, the same
hardware can support a larger city.

## Files Affected

- `ww_agent/src/loops/fast.py`
- `ww_agent/src/loops/slow.py`
- `ww_agent/src/loops/doula.py`
- `ww_agent/src/resident.py`
- `ww_agent/src/identity/loader.py`
- `ww_agent/src/loops/wander.py`
- `ww_agent/src/memory/voice.py`
- `ww_agent/src/main.py`
- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/src/api/game/state.py`
- `worldweaver_engine/src/services/turn_service.py`
- `worldweaver_engine/src/services/federation_pulse.py`
- `worldweaver_engine/src/models/__init__.py`
- `worldweaver_engine/tests/api/test_world_endpoints.py`
- `worldweaver_engine/tests/api/test_route_smoke.py`
- `prune/majors/06-agent-life-visibility.md`
- `prune/majors/19-fractal-shard-workspace.md`

## Acceptance Criteria

- [ ] Residents can enter a first-class `resting` state that is stored in runtime state and survives normal loop execution
- [ ] Resting residents stop behaving like fully reactive ambient participants for the duration of the rest window
- [ ] The slow loop can trigger rest from meaningful reflective or social pressure, not just random timers
- [ ] Entering and exiting rest can produce plausible movement or offstage transitions when appropriate
- [ ] World digest / roster output distinguishes active residents from resting or offstage residents
- [ ] Resting residents consume materially less inference activity than active residents
- [ ] Shard operators can tune or inspect rest-cycle behavior through explicit configuration and metrics
- [ ] The system supports both ordinary daily sleep windows and short chosen decompression breaks
- [ ] A resident can narratively and behaviorally "step away" in a way that the world model actually honors
- [ ] Effective shard capacity improves because not all residents remain inference-hot all day
- [ ] Residents have loose daily rhythm anchors that distribute them across the city more plausibly over time

## Risks & Rollback

- If rest is implemented as pure disappearance, the world may feel emptier rather than
  more believable. Rest must distinguish between absence, low availability, and
  true offstage withdrawal.
- If the thresholds are too aggressive, agents may become inert or miss social
  opportunities. Start with conservative dormancy and observable metrics.
- If the scheduling logic is too rigid, rest will feel mechanical rather than
  character-shaped. Identity and routine should influence it.
- If routine anchors are too rigid, residents will feel path-scripted rather
  than city-shaped. Roll back by keeping anchors probabilistic and pressure-based.
- If roster/digest projection is not updated alongside loop behavior, users will still
  see agents as present and available even when they are logically resting.
- Rollback path: land the runtime state fields and projection plumbing first, keep
  dormancy gating feature-flagged, and fall back to the current always-active loop
  behavior if the first scheduling pass proves too disruptive.
