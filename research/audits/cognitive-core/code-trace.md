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
- `settling`: a low current value at least five minutes after the prior model call;
- `fervor`: a middle-high current value at least three minutes after the prior model call;
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
9. **The pulse contract misstates the causal role of `felt_sense`.** It is not sent directly to the effector,
   but later code mines it for anchors, returns it through elective recall, and may feed those anchors into
   arousal when anchor gating is enabled. It is not “readout only” in the ordinary causal meaning.
10. **Unsupported prediction scopes manufacture surprise.** The model is invited to predict fields at `here`
    or a named person, but ordinary stimulus has only `self` features and optional `anchors`. Missing observed
    scopes are treated as zero, so an unmeasured place/person prediction becomes a false mismatch.
11. **Much of the pulse schema is write-only.** Drive nudges, trace verdicts, and staged `new_reverie` and
    `goal_update` fields have no production reader. Comments still describe some of them as live mechanisms.
12. **The resident-private/shard-public boundary is broken.** The runtime mirror copies all reduced inner
    projections to engine session variables. The raw session-variable GET route has no authentication or
    ownership check, while public roster data exposes session IDs. The city briefing's absolute privacy claim
    does not match the code.
13. **Direct social pressure does not resolve honestly.** The newest direct question is always inside an
    expiry window measured relative to itself. Packet observation and reply-edge evidence do not close it, so
    “awaiting reply,” `owes_reply_to`, and maximum social pull can survive an actual reply.
14. **The advertised drive/constitution path is only partly wired.** Identity resonance affects prompt
    selection, chatter ranking, optional anchors, and venture targets. It does not tag surprise valence, does
    not include reveries in the live drive build, and does not supply the promised semantic contradiction gate.
15. **Current and historical social state are conflated.** Prompt delivery stops showing observed packets, but
    subjective reduction keeps counting them. This creates model calls with social pressure but without the
    source words that supposedly caused it.
16. **Anchor continuity is recursive prompt state.** Model self-report is mined, called current inner concern,
    shown back to the model, and optionally admitted into call timing. It is not independent evidence.
17. **Selected memory has two durable homes.** `kept_memory.jsonl` still claims to protect memory from a ledger
    trim removed by Major 85. The side file is treated as authority rather than as a rebuildable index.
18. **Normal tick cost still grows with history.** Append and checkpoint updates are bounded, but the core,
    substrate stimulus, queues, prompt producer, memory rescue, and mirror retain full-ledger read paths.
19. **An empty ambient observation cannot clear prior pressure.** Perception emits an ambient snapshot only
    when signals are non-empty. Featureless calm can therefore leave an older crowding/event/weather record as
    current state until another non-empty ambient record arrives.
20. **Poll cadence changes call pressure.** The same mismatch is appended once per observation while decay
    uses wall time. The 0.5-second bounded runner is not a time-compressed form of the 20-second natural run.
21. **Settling and fervor do not measure their claimed durations.** Both use time since the last model call,
    not time since entering the relevant numeric band. A brand-new event can inherit minutes of false calm or
    false restlessness.
22. **A new direct address can be hidden by social-node saturation.** Exact-place packets remain pending, but
    another address may not change an already-maxed node, city speech has no event-level force-attention hook,
    and settling prompts withhold the pending words.
23. **The waveform vital is an operational heuristic, not a health reading.** It counts idle attempts as
    discharge without resetting ordinary pressure, omits the absence term from its reconstruction, and uses
    threshold-dwell approximations that can diverge from the decaying curve.
24. **Elective reading begins only after a host-scheduled model call.** The model chooses a named source from
    inside an activation episode, but no durable resident-owned task can schedule or resume a long inquiry.
25. **One pulse may contain several LLM calls.** The default two-read limit permits an initial call plus two
    continuations. “Single LLM call” comments describe the pre-reach design, not the live implementation.
26. **Only the final continuation pulse becomes durable.** Earlier memories, expectations, self edits, drive
    nudges, trace verdicts, and felt reports are discarded unless the model repeats them in the final response.
27. **Duplicate-read timing is not replayable.** The cache ignores the supplied `now`, uses process-local
    monotonic time, disappears on core rebuild, and can close a fresh model episode without presenting the
    cached result to that episode.
28. **The read cap is not a cost budget.** It counts sources, while model calls, input size, output tokens,
    latency, and provider price remain variable. It is a useful circuit breaker with a misleading unit.
29. **The continuation's “frozen world” is only partly frozen.** Initial perception and the source catalog
    stay fixed, source providers may read live shard state, and the final action reaches the live engine.
30. **Direct address is still prompt-level response pressure.** The shared contract instructs the model to
    choose a non-null act when addressed instead of merely ensuring the event reaches attention.

## Questions for the next code pass

- Which private projections, if any, does a city actually need beyond explicit operational status?
- Which exact experimental flags and prompt hashes were effective in each recorded run?
- Can paired replays isolate afterimage, baseline, anchors, drive resonance, memory recall, prompt examples,
  and mode wording one at a time?
- Which constants were calibrated against recorded behavior, and which were selected by intuition?
- Can prompt pressure be reduced enough that a substrate ablation measures the substrate rather than the
  prose describing it?
- What is the smallest durable inquiry lifecycle that lets a resident resume chosen reading while keeping
  event delivery and steward resource limits separate?
