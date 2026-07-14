# Rest as a substrate capacity, not a loop-era scheduler

## Decision and lineage

Major 83 slice 1a deleted `ww_agent/src/runtime/rest.py` — the loop-era rest scheduler — as
verified-dead code (zero importers; it read `LoopTuning` and engine weather config, both
loop-era seams). During that cut, the audit's claim that its engine twin was also dead was
**corrected**: `GET /world/rest-metrics` is live — `wwClient.getRestMetrics()` feeds the
`PresencePanel` in `WorldInfoPane`, and `AppTopbar` gates on it. The UI expects residents that
rest; nothing in the runtime produces a resting state anymore.

- **Status:** proposed (2026-07-12, keeper's call during Major 83 slice 1: *"the agents should
  have the capacity to rest — if that's not an element of the code, it needs to be seeded as a
  major."*)
- **Owns:** giving rest a substrate-native home. The deleted `rest.py` is **not** the design to
  restore — it was an external scheduler mutating loop tuning, the same shape of outside-in
  behavior control Major 68 killed for guild signals.
- **Coordinates with:** Major 49 (the substrate already has the ingredient: circadian
  wakefulness scales the pulse rhythm so a shard quiets after dark); Major 83 slice 2 (the
  rest-metrics endpoint survives route triage as a documented surface); the-stable
  reconvergence (Major 76) if rest derivation matures there first.

## Problem

Residents cannot rest, but three surfaces assume they can:

- `worldweaver_engine/src/api/game/world.py::get_world_rest_metrics` reports "resting sessions
  and tuning overrides" — with no producer, it reports vacuously.
- The client `PresencePanel` renders per-session rest state to players/stewards.
- The substrate's circadian wakefulness (Major 49) quiets the pulse rhythm after dark, but that
  quieting is invisible: it never becomes a legible "resting" state in session vars, so the
  world can't distinguish a resting resident from a stalled one.

That last point is also operational: without a rest state, "quiet because asleep" and "quiet
because broken" look identical to the keeper.

## Proposed Solution

Derive rest, don't schedule it — consistent with "the ledger is the only state":

1. **`derive_rest` reducer** in `ww_agent/src/runtime/salience.py` (or a sibling): a resident is
   resting when circadian wakefulness is low AND arousal has stayed below the settling floor for
   a sustained window. Pure read-time derivation over the ledger; no new writer, no scheduler,
   no external override of the mind (the Dwarf-Fortress law — rest must *arise* from the
   substrate, never be imposed on it).
2. **Mirror it out:** `ResidentRuntimeMirror.sync_once` already syncs reduced state to session
   vars; add the derived rest state (`_resident_rest: {resting, since, wakefulness}`) to that
   payload.
3. **Engine reads what the mirror writes:** `get_world_rest_metrics` reports the mirrored rest
   state instead of (or alongside) its current tuning-override inspection. PresencePanel keeps
   working with real data.
4. **Optional depth later:** rest as more than absence — reverie/consolidation pulses during
   rest windows (ties to the settling/fervor "making" gear) — deferred; out of scope here.

## Files Affected

- `ww_agent/src/runtime/salience.py` (new `derive_rest` reducer + tests)
- `ww_agent/src/runtime/mirror.py` (include rest state in session-var sync)
- `worldweaver_engine/src/api/game/world.py` (`get_world_rest_metrics` reads mirrored state)
- `worldweaver_engine/tests/api/test_world_endpoints.py` (rest-metrics tests updated to the
  mirrored contract)
- `ww_agent/tests/` (reducer tests: rest derives from wakefulness + arousal lull; ends on
  ignition)

## Acceptance Criteria

- [ ] A resident whose shard enters circadian night and whose arousal stays below the settling
      floor derives `resting=true` from the ledger alone (no new event writer required)
- [ ] Ignition (or wakefulness rising) ends rest with no scheduler involvement
- [ ] `ResidentRuntimeMirror` publishes the rest state to session vars; `/world/rest-metrics`
      reports it; PresencePanel shows a resting resident during shard night
- [ ] Nothing outside the substrate can set or clear a resident's rest state
- [ ] Agent + engine suites green; `check` green

## Risks & Rollback

- **Threshold tuning:** a too-eager rest derivation would mark lulled-but-awake residents as
  resting. Mitigate with conservative windows and a keeper-visible `wakefulness` value alongside
  the boolean; tune from observed shard nights.
- **Contract drift:** the rest-metrics response shape changes; the client PresencePanel and its
  tests move in the same change (single coordinated PR, matching the endpoint's existing tests).
- **Rollback:** the reducer is read-time and additive — reverting the mirror/endpoint change
  restores current (vacuous) behavior with no data migration.
