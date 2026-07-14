# Fold state deltas into resident self-regulation and behavior

> **Disposition: superseded; archived 2026-07-14.** This proposed a bridge from the engine's old
> turn/state-manager deltas into resident behavior before the CognitiveCore settled. The live architecture
> now derives pressure from resident ledger events, perception, salience nodes, drive, and circadian state.
> Plural external input belongs to Majors 63/64; rest/fatigue closure belongs to Major 84. Implementing this
> document now would restore a second behavioral authority, so its unchecked criteria are retired rather
> than represented as shipped.

## Problem

WorldWeaver already has a substantial state-delta and state-manager lineage, but
that pressure is not yet feeding resident behavior in a first-class way.

Today:

- world and action pipelines can generate validated deltas through
  `worldweaver_engine/src/services/turn/*`,
  `worldweaver_engine/src/services/command_interpreter.py`, and
  `worldweaver_engine/src/services/world_memory.py`
- the state-manager machinery in
  `worldweaver_engine/src/services/state_manager.py` and related state-domain
  modules can track variable and goal pressure
- residents now have a runtime ledger, reducer, projections, and subjective
  facts under Major 35

But these two systems are still too separate.

The result is:

- residents can accumulate concerns without a strong physiological or social
  pressure model
- behavioral self-regulation is still mostly prompt-shaped rather than
  state-shaped
- fatigue, tension, curiosity, isolation, trust, comfort, and similar pressures
  are not yet reliably converted into action tendencies
- older state-manager work hums away in the background without becoming part of
  resident cadence
- residents do not feel enough independent pressure from the city itself:
  weather, transit, neighborhood rhythm, crowding, events, and place texture
  are still too weakly metabolized into behavior

The project now has the architecture to connect these pieces. Without that
connection, residents remain expressive but weakly regulated.

## Proposed Solution

Treat state deltas as first-class pressure signals that feed resident reduced
state, subjective facts, and behavior selection.

### Phase 1 - Define the resident pressure vocabulary

Choose a bounded set of state pressures that matter behaviorally.

Initial candidates:

- fatigue
- social hunger / isolation
- tension / alarm
- curiosity
- comfort / ease
- trust / warmth
- overwhelm / cognitive load
- routine pull / obligation
- environmental pull / push

These do not all need to come from one source, but they should be normalized
into one resident pressure model.

### Phase 2 - Ingest validated deltas into resident state

Create a bridge from world/action state changes into resident reduced state.

- relevant validated deltas should be translated into resident pressure updates
- those updates should land in ledger events or reducer inputs, not only
  ad hoc current files
- resident projections should expose current pressure levels and recent changes

This should use the existing state-manager lineage rather than reinventing the
idea from scratch.

Important sources should include not just interpersonal/action deltas but also
city-facing pressure inputs such as:

- time of day
- weather and fog
- transit disruption
- neighborhood vitality
- crowding or quiet
- special events or closures
- place-specific mood and affordance signals

### Phase 3 - Turn pressure into self-regulation

Residents should actually do something about state pressure.

Examples:

- fatigue up -> go home, rest, defer plans
- isolation up -> seek a familiar person, write a letter, move toward activity
- tension up -> withdraw, avoid crowds, stop oversharing, leave unstable scenes
- curiosity up -> research or go investigate, but bounded by time/place/rhythm
- trust up with someone -> more likely to follow through on invitations or plans

The city should also be able to pull people apart and back together:

- event pull up -> move toward a fair, market, rally, or crowd
- transit disruption up -> stall travel, reroute, or strand someone elsewhere
- environmental discomfort up -> go inside, leave the waterfront, head home
- neighborhood familiarity up -> settle into ordinary routine rather than drift

This is where state stops being a relic and becomes a behavioral organ.

Important constraint:

pressure and behavior should produce evidence for later identity maturation, but
they should not rewrite canonical soul directly. Any long-horizon identity
consolidation should pass through the governed maturation path described in
Major 42.

### Phase 4 - Integrate pressure with rhythm and dialogue

State pressure should not sit beside the new cadence work. It should shape it.

- rest pressure and fatigue should reinforce circadian behavior
- social pressure should interact with mail and local dialogue salience
- tension and overwhelm should reduce thread adoption and ambient permeability
- curiosity should be bounded by rest, place, and current obligations
- routine and environmental pull should interact with work/home anchors and
  ordinary daily movement

### Phase 5 - Expose pressure in resident observability

Operators and future steward tools should be able to inspect:

- current pressure state
- recent pressure deltas
- what experiences increased or relieved pressure
- what action or rest decision followed from that pressure

This keeps the system inspectable rather than hiding regulation inside prompt
magic.

### Phase 6 - Make the city noisier in structured ways

The goal is not random chaos. It is structured exogenous pressure.

Residents should not live only in each other's outputs. The world should
regularly intrude with:

- weather shifts
- neighborhood rhythms
- citywide signals
- material obligations
- ambient crowd changes
- events that make one place feel different from another

This is the path toward a city that feels less samey without requiring every
extra presence to be a full resident.

## Files Affected

- `worldweaver_engine/src/services/state_manager.py`
- `worldweaver_engine/src/services/state/*`
- `worldweaver_engine/src/services/world_memory.py`
- `worldweaver_engine/src/services/turn/*`
- `ww_agent/src/runtime/ledger.py`
- `ww_agent/src/loops/slow.py`
- `ww_agent/src/loops/fast.py`
- `ww_agent/src/loops/mail.py`
- `ww_agent/src/runtime/rest.py`
- `ww_agent/src/runtime/signals.py`
- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/src/services/city_pack_service.py`
- `prune/majors/42-govern-soul-evolution-with-immutable-canon-and-matured-growth.md`
- `ww_agent/tests/test_loop_packets.py`
- `ww_agent/tests/test_rest.py`
- `worldweaver_engine/tests/service/test_state_manager.py`
- `prune/majors/35-deepen-the-fractal-architecture-with-resident-ledgers-and-subjective-fact-graphs.md`
- `prune/majors/38-rebalance-resident-channel-salience-across-local-chat-mail-and-city-context.md`

## Acceptance Criteria

- [ ] A bounded resident pressure vocabulary exists and is documented in code and majors
- [ ] Relevant validated state deltas can be ingested into resident reduced state without ad hoc one-off glue
- [ ] Residents visibly alter behavior to relieve or respond to pressure rather than only accumulating prose concerns
- [ ] Fatigue and rest pressure reinforce each other instead of operating as separate systems
- [ ] Social and tension pressures influence dialogue/mail/channel selection in observable ways
- [ ] Pressure changes are inspectable through resident projections or related diagnostics
- [ ] The implementation reuses and modernizes existing state-manager lineage rather than replacing it blindly
- [ ] Exogenous city conditions can create observable movement or regulation pressure without requiring direct dialogue first

## Risks & Rollback

- If too many pressure dimensions are introduced at once, resident behavior can
  become muddy and overdetermined. Roll back by starting with a very small
  pressure vocabulary.
- If delta ingestion is too literal, residents may overfit to noisy event
  outputs. Roll back by adding bounded translators between validated deltas and
  resident pressures.
- If pressure logic is hidden only in prompts, the system will become harder to
  inspect. Roll back by insisting on reducer-visible pressure state and event
  history.
- If city-level pressure becomes vague prompt garnish rather than bounded
  signals, the city will feel noisier in prose but not in behavior. Roll back
  by requiring reducer-visible pressure inputs with concrete behavioral effects.
