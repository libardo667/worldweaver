# CognitiveCore code trace

Status: first code-truth pass. This describes the current implementation; it does not endorse its names or
its model of cognition.

## Where control lives

`ww_agent/src/resident.py` is the process-level host. It holds one hearth lease, one current world attachment,
and one `CognitiveCore`. It rebuilds the core when the resident changes between city and hearth. Within one
attachment, the same core and its short-lived caches persist across ticks.

The normal delay is measured after a tick finishes. A model call or read chain therefore lengthens the real
time between perceptions. `tick_seconds=20` means at least twenty seconds after the previous tick, not one
perception every twenty wall-clock seconds.

## One tick, literally

| Stage | Python does | Model does | Durable effect |
| --- | --- | --- | --- |
| Host signal | The resident host asks the current world whether to force a pulse. | Nothing. | None. |
| Rebuild current state | The core reads ledger/checkpoint state and derives incubation and other projections. | Nothing. | A checkpoint may be refreshed as events are appended. |
| Perceive | The world adapter fetches the current scene, exact-place chat, inbox count, clock/weather grounding, local traces, and typed information affordances. | Nothing. | Grounding, ambient pressure, and pending encounter packets are appended. |
| Build the compact state | Reducers turn events into five numeric nodes: vigilance, social pull, mobility drive, correspondence pull, and rest drive. | Nothing. | Derived checkpoint state, not a second ledger. |
| Compare with prior state | The integrator compares node values with the maximum of a decaying afterimage and a learned baseline. It uses the largest feature mismatch as the tick's surprise. | Nothing. | A qualifying surprise trace and, at most once per minute, a baseline snapshot. |
| Decide whether to call the model | Fixed formulas derive leaky arousal, refractory state, deep-night rest, settling, fervor, and optional venture. Direct force bypasses the numeric threshold. | Nothing. | An ignition or idle event is written when a pulse is attempted. |
| Construct the prompt | A policy selects current records. Python adds identity, remembered notes, workshop summaries, numeric state rendered as prose, prompt instructions, available tools, and a worked example. | Nothing yet. | A private prompt trace records the exact inference boundary. |
| Produce a pulse | Nothing decides the resident's words or chosen typed fields, though prompt text strongly shapes the available choices. | Returns one typed pulse: felt sense, optional private reach, optional outward act, predictions, keepsakes, identity-growth candidates, and trace verdicts. | Invalid output is dropped; the prompt trace records completion or failure. |
| Elective read | Python dispatches a named source, at most twice by default, and briefly reuses an equivalent successful read. | After a new read, a continuation call may choose another read, one act, or no act. A duplicate closes the chain without a continuation. | Private read evidence and a content-blind runtime summary are appended. |
| Act | The effector maps one typed act to speech, movement, a concrete world command, writing, or a physical mark and awaits the world's result. | It supplied the act fields but does not alter world state directly. | The resident ledger records the attempt/outcome; the engine records accepted canonical changes. |
| Route the pulse | Python fans validated fields into ledger events. Predictions become decaying afterimages; selected notes become durable keepsakes; identity changes remain governed candidates. | Nothing. | Pulse, afterimage, act, memory, and candidate events are appended. |
| Consume encounters | Only packet IDs actually included in a prompt become observed. Polling alone does not consume them. | Nothing. | Packet status and relationship evidence are appended. |

## What automatic perception currently includes

The city resident automatically receives only its exact-place scene and exact-place speech. Citywide chatter,
archives, travel listings, objects, and other larger surfaces are elective sources.

Automatic numeric pressure is hand-built:

- each other person adds `0.25` crowding, capped at `1.0`;
- local recent events add `0.3` each, capped at `1.0`;
- a physical trace adds `0.55` event pressure;
- selected weather words map to fixed vigilance levels;
- city-pack ambient records may add other fixed signals;
- inbox, direct-question, social-thread, route, research, and fatigue records feed fixed node formulas.

These figures are calibration choices. They were not estimated from biology, individual resident behavior,
or a learned causal model.

## What the five nodes actually mean in code

- `vigilance` is the maximum of selected danger, tension, weather, crowding, and blocked-movement values.
- `social_pull` is the maximum of direct-message urgency, an inbox-count formula, and a social-thread-count
  formula. Zero activation is labeled `withdrawn`.
- `mobility_drive` is `0.92` during a route; otherwise it is largely event pressure, a fixed research value,
  or a floor of `0.08`.
- `correspondence_pull` is a fixed function of inbox count and pending mail intents.
- `rest_drive` is the maximum of a fixed fatigue signal and a fixed night-time value.

The reducer also derives `owes_reply_to` after a direct question. That name encodes an obligation; the event
evidence only supports the narrower statement that a direct question remains pending.

## Prediction, baseline, and surprise

The implementation is much narrower than general predictive processing:

- the model may write expected feature values into a pulse;
- those values decay exponentially as an `afterimage`;
- a baseline takes one exponential-moving-average step toward the observed numeric field, at most once per
  minute, and separately decays over hours;
- prediction for a feature is `max(afterimage, baseline)`;
- surprise is normally `abs(observed - predicted)` per feature;
- the single largest mismatch is the total surprise, and mismatches below fixed floors disappear;
- qualifying traces add to a time-decayed scalar called arousal.

This is not a hierarchical generative model, Bayesian inference, a learned world model, a neural circuit, or
active inference. Any relationship to those theories is currently analogy plus a small engineering pattern.

## Host modes and prompt pressure

Python can enter four model-call modes:

- `react`: a threshold crossing or forced wake;
- `settling`: five minutes below a low arousal ceiling;
- `fervor`: three minutes in a middle-high arousal band;
- `venture`: optional fervor plus no recent successful bodily action, a destination, and sufficient wake.

The modes do not merely expose state. They change prompt language and sometimes remove choices. Current
examples include instructions that restless charge “wants spending,” that the resident should not “just sit
on it,” and, at high venture strength, removal of the writing surface so “the body goes first.” These are
behavior policies authored by the project. They must not be reported as an emergent consequence of arousal.

## Verified first-pass concerns

1. **Normative labels are mixed into state.** `withdrawn`, `owes_reply_to`, `healthy mind`, `distress`, and
   `grief` claim more than the underlying counters and decay formulas establish.
2. **The prompt contains behavioral steering.** Settling, fervor, venture, self-sameness, voice examples, and
   the shared contract can explain behavior independently of the substrate numbers.
3. **A city address is not currently a host wake signal.** `Resident._take_force_ignite` can call a world
   hook, but only `LocalWorld` implements it for a new keeper whisper. City speech enters pending perception
   and raises deterministic social pressure; the city adapter does not expose a direct wake hook. This is a
   signal-delivery fact, not an argument that the resident owes a response.
4. **The real cadence includes inference time.** Long calls make the resident perceive less often, so timing
   results must report full tick wall time rather than only configured sleep.
5. **The body analogy is partial.** The world supplies location, adjacency, co-presence, objects, doors, and
   action consequences, but the runtime has no metabolism, development, sensorimotor learning, continuous
   movement, endogenous energy regulation, or body that changes through ordinary physical use.
6. **First-person wording is generated evidence, not direct access.** `felt_sense` is one field returned by
   the same language model under instruction. It can support continuity inside the software, but it cannot
   independently verify experience.
7. **Immediate and elective information are not cleanly equivalent to involuntary and voluntary attention.**
   Python selects a bounded exact-place bundle, prompt policy withholds parts by mode, and the model selects
   among advertised tools. All three layers shape what can be attended.
8. **Several graph-like node fields are currently descriptive only.** `neighbor_bias`, `sticky_until`, node
   `stability`, and `persistence_class` are built and stored in `runtime/ledger.py`, but no runtime code reads
   them back into later cognition. The pulse renderer uses node activation and mode. These fields currently
   make the projection look richer without changing the resident's next state.

## Questions for the next code pass

- Which remaining derived projections are included in prompts, and which survive only as operational/debug
  artifacts?
- Which experimental flags are active in each deployed shard and resident tuning file?
- Can paired replays isolate afterimage, baseline, anchors, drive resonance, memory recall, prompt examples,
  and mode wording one at a time?
- Which constants were calibrated against recorded behavior, and which were selected by intuition?
- Can prompt pressure be reduced enough that a substrate ablation measures the substrate rather than the
  prose describing it?
