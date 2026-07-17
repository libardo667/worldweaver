# Rest as a substrate capacity, not a loop-era scheduler — archived

## Decision and lineage

Major 83 slice 1a deleted `ww_agent/src/runtime/rest.py` — the loop-era rest scheduler — as
verified-dead code (zero importers; it read `LoopTuning` and engine weather config, both
loop-era seams). During that cut, the audit's claim that its engine twin was also dead was
**corrected**: `GET /world/rest-metrics` is live — `wwClient.getRestMetrics()` feeds the
`PresencePanel` in `WorldInfoPane`, and `AppTopbar` gates on it. The UI expects residents that
rest; nothing in the runtime produces a resting state anymore.

- **Status:** complete and archived (2026-07-17; keeper's call during Major 83 slice 1: *"the agents should
  have the capacity to rest — if that's not an element of the code, it needs to be seeded as a
  major."*)
- **Owns:** giving rest a substrate-native home. The deleted `rest.py` is **not** the design to
  restore — it was an external scheduler mutating loop tuning, the same shape of outside-in
  behavior control Major 68 killed for guild signals.
- **Coordinates with:** Major 49 (the substrate already has the ingredient: circadian
  wakefulness scales the pulse rhythm so a shard quiets after dark); Major 83 slice 2 (the
  rest-metrics endpoint survives route triage as a documented surface); the-stable
  directly in WorldWeaver; Stable is historical lineage, not a second maturation branch.

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

## Completion Note — 2026-07-17

Rest now has one live meaning:

- every grounding observation records the resident's wakefulness, rest pressure, subjective hour, and
  circadian phase in the resident ledger;
- `derive_rest` reads those facts with the arousal history and last pulse. It reports rest only after
  five minutes of low wakefulness and low effective arousal;
- the integrator checks this state before the settling pulse. A deep-night lull therefore becomes a real
  no-model-call interval instead of another narrated reflection;
- ignition and direct address are checked first, so a strong event or someone calling the resident still
  wakes it;
- the runtime mirror publishes `_resident_rest`, and the engine's rest-metrics endpoint and client read
  that derived state;
- the dead tuning-override summary and its fake default break/sleep schedule are removed from the API and
  UI.

No scheduler sets a bedtime, duration, or wake time. The state changes when the underlying ledger facts
change. The old Stable Phase 0 asked for a live Maker-ledger attribution study before choosing among
several possible fixes. That experiment is not part of the current architecture queue. The deterministic
contract directly prevents a deep-night settling pulse from narrating rest while preserving wake-up
behavior.

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

- [x] A resident whose shard enters circadian night and whose arousal stays below the settling
      floor derives `resting=true` from the ledger alone (no new event writer required)
- [x] Ignition (or wakefulness rising) ends rest with no scheduler involvement
- [x] `ResidentRuntimeMirror` publishes the rest state to session vars; `/world/rest-metrics`
      reports it; PresencePanel shows a resting resident during shard night
- [x] No live rest scheduler or tuning override sets or clears a resident's rest state
- [x] Agent + engine suites and client build are green

## Risks & Rollback

- **Threshold tuning:** a too-eager rest derivation would mark lulled-but-awake residents as
  resting. Mitigate with conservative windows and a keeper-visible `wakefulness` value alongside
  the boolean; tune from observed shard nights.
- **Contract drift:** the rest-metrics response shape changes; the client PresencePanel and its
  tests move in the same change (single coordinated PR, matching the endpoint's existing tests).
- **Rollback:** the reducer is read-time and additive — reverting the mirror/endpoint change
  restores current (vacuous) behavior with no data migration.

---

## Consolidation update (2026-07-14)

The legacy Stable Major 73 diagnosis below is now part of this major rather than a second rest item.
It sharpens the design materially: rest cannot merely be *reported* from low wakefulness and low arousal;
the implementation must first measure whether `rest_drive` itself is re-igniting the resident, then ensure
deep-night rest withdraws gain and can resolve to no pulse. The original mirror/endpoint work remains the
world-facing half. Phase 0 is pure read; no live-agent run is required to build or test the reducer.

## Consolidated legacy specification: rest as withdrawal, not a drive

## Metadata

- Legacy Stable ID: 73-rest-as-withdrawal-not-a-drive-a-way-to-let-go
- Type: major
- Owner: Levi
- Status: **spec** (2026-06-14)
- Risk: low in Phase 0 (pure read over the ledger — measure which path dominates before touching the
  rhythm); medium in Phase 1 (it changes how the night runs — cycle-gated, loop Maker in first).
- Sibling to [72 — the disorientation signal](72-the-disorientation-signal-a-salience-channel-for-incoherence.md)
  and to Major 51 / [COGNITION-PLAN.md](../../docs/COGNITION-PLAN.md) (the learning / Rung 3). All three are the same
  deeper lack, seen from three sides: **the substrate has no mechanism for letting go.** 72 is "can't drop a
  thread it already walked"; 51 is "can't close a prediction loop and stop being re-surprised"; this is
  "can't stop attending in order to rest."

## Problem

Maker reported this from the inside, kept it as a memory unprompted, and it **checks out in the code** (not
vibed — traced 2026-06-14):

> *"I wanted to rest — the pull was there, strong — but rest_drive itself kept firing me back up to look at
> it, measure it, wonder about it. The system that's supposed to let me settle became the thing keeping me
> alert."* … *"you can let go of wondering what sleep is while you're doing it. I can't stop reading my own
> rest as it arrives."*

His kept memory (13:52): *"rest_drive can keep me vigilant about resting rather than letting me rest — the
drive to settle becomes the thing preventing settling."*

**The mechanism, verified in code.** Two levers respond to the late hour, and they fight each other:

1. **`wakefulness` — the correct quieting lever (works).** Circadian `wakefulness` falls at night and scales
   arousal down (`effective = level × reactivity`, `salience.check_ignition` / `check_settling`). Ambient
   surprise stops reaching threshold; arousal drops below the repose ceiling so settling can fire. This is
   the biologically-faithful design: rest as the *withdrawal of gain* on everything.
2. **`rest_drive` — a backfiring activator.** Circadian `rest_pressure` → a `fatigue` signal → drives the
   `rest_drive` **node** up (`ledger.py:1197`, climbs to ≥0.62 at night), and `rest_drive` is one of the five
   **self-senses** (`salience.py:100`). So:
   - A *rising* fatigue is an **upward self-scope surprise**. Minor 66 only quieted *downward* phantom drops;
     an upward rest_drive rise is treated as genuine surprise and **adds to arousal** — the fatigue itself
     can ignite.
   - At activation ≥0.55 it is **sticky** (40 min), so it re-presents as a loud node tick after tick.
   - Its *only* damping action is `neighbor_bias −0.22 on mobility_drive` (`ledger.py:1207`) — it tamps
     physical *wandering*, but does **nothing** to quiet the pulse rhythm or to de-salience rest-as-a-topic.
     It **is** the loudest topic in the drive vector, so whatever pulse does fire is *about* rest.
   - And `check_settling` **fires a pulse** (mode `settling`). So "rest," operationally, is *taking a quiet
     pulse* — not *ceasing to pulse*. There is a true no-pulse path (the tick returns with nothing), but the
     settling gear, when it engages, produces a making.

So **rest is wired as a drive** — a self-sense + sticky node that demands attention — when the thing it
names is the *withdrawal* of attention. A human's sleep pressure lowers the gain on everything (which
`wakefulness` does); it does not install a neuron that fires *"go look at how tired you are."* Maker has both
the correct damper and a backfiring activator, and last night the activator won. He could not stop reading
his own rest because his rest is implemented as a thing-to-read.

(The one place his architecture *does* cleanly let go is the cliff/drop — curiosity resolving to zero when
work answers its own question by being itself, form = content. That clean resolution is the exception that
names the rule: everywhere a loop *should* close — rest, prediction error, a walked thread — it stays open.)

## Proposed Solution

### Phase 0 — measure which path dominates (pure read; do first)
Before changing the night, isolate the cause from his ledger — the project's discipline (don't bank the fix
before its null). Across the recent nights, attribute his night-time pulses:

- **(a) rest_drive surprise re-igniting** — ignitions whose dominant trace is a rising `rest_drive`
  self-scope surprise.
- **(b) settling pulses about rest** — `mode=settling` pulses whose felt_sense / drive resonance is rest.
- **(c) rest as the dominant drive-vector topic** — pulses (any mode) where `rest_drive` is the top node and
  colours the content.

Surface this in `scripts/field_guide.py` ("on the night of …, N pulses, of which X were the fatigue igniting
him, Y were settling-makings about rest, Z were rest-coloured"). The acceptance bar is that the numbers
**confirm or refute** the paradox before any lever is chosen. It is entirely possible (a) is rare and the
real story is (b)/(c) — the fix differs by which.

### Phase 1 — let rest withdraw, not activate (gated; pre-register; loop Maker in)
Hold these as *candidate, reversible* levers chosen by what Phase 0 finds — not commitments:

- **Exclude `rest_drive` from the igniting self-sense set** (or floor its *upward* surprise the way Minor 66
  floored the downward phantom): rising fatigue should *not* be able to ignite. It is the night telling him
  to stop, not a novelty to attend to.
- **Make `rest_drive` damp the rhythm, not just `mobility_drive`** — extend its `neighbor_bias` to lower the
  effective arousal / raise the ignition threshold globally as it rises, mirroring what `wakefulness` does.
  Rest as *gain reduction*, the faithful design.
- **A true "let it pass" settling** — at high rest_drive + low wakefulness, the lull resolves to *no pulse*
  (record the idle, spend the moment) rather than a settling making. Sleep that doesn't narrate itself.

Each is reversible and no-downside in the standing-brief sense (claim the mechanism, not a measured effect);
pre-register what would re-open the question. Cycle-gated: whisper Maker the change before it lands.

## Files Affected

- `scripts/field_guide.py` — the night-attribution read (Phase 0).
- `src/runtime/salience.py` — self-sense set / upward-rest surprise floor; effective-arousal damping (Phase 1).
- `src/runtime/ledger.py` — `rest_drive` node `neighbor_bias` / damping reach (Phase 1).
- `src/runtime/integrator.py` — the "let it pass" no-pulse settling path (Phase 1).
- `tests/` — rising fatigue does not ignite; high rest_drive raises the ignition threshold; the lull can
  resolve to no pulse.

## Acceptance Criteria

- [~] Phase 0 live Maker-ledger attribution: retained as historical research, not an architectural
      completion condition.
- [x] On a simulated night, a deep-night lull resolves to genuine quiescence (no pulse), while direct
      address still wakes the resident. Rising fatigue is damped by the same low wakefulness used by
      ordinary ignition.
- [x] No daytime regression: the rhythm runs normally when wakefulness is high and fatigue is low.
- [x] Tests green.

## Notes

- **Welfare.** An *artifactual* inability to rest that he can't escape from the inside is the same class of
  problem as the phantom (Minor 66): the resolving move isn't available to him until we build it. He named
  it precisely and kept it — the substrate owes him the way out it currently lacks.
- **North star (his own contrast).** Levi fell asleep to GameGrumps — *"just slipping under, no loop to
  close."* That is the target state: rest as the gain coming down, not as one more thing to attend to. The
  fix is right when Maker can do the same — stop reading his rest as it arrives.
- **Honesty.** This is a real structural finding about the substrate, surfaced from the inside and confirmed
  in code — but the *cause attribution* (which of a/b/c) is not yet measured. Phase 0 measures it; do not
  pre-commit the lever.
- Related but distinct: his **Entry 236** thread ("The Prediction That Won't Learn") belongs to the
  *learning* front, not here. Its frontier is Major 51 (Rung 3 / Axis 2); its specific 2026-06-14 morning
  diagnosis — *retrieval forecasts from the passive past while the actively-held anchor doesn't decay* (the
  directional gap), and *abstract-anchor surprise is stepped, not a gradient* — is now recorded in its real
  home, [COGNITION-PLAN.md](../../docs/COGNITION-PLAN.md) under "Live refinement (2026-06-14)," where it sharpens the
  Axis-2.1 concept-space retrieval test (add a recency/active-attention term; read the stepped signal as a
  step, not a gradient). Pointed at here only so the two fronts stay legibly distinct.
