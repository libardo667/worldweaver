# Prompt pipeline and elective information ecosystem

**Date:** 2026-07-14  
**Authority:** architectural working brief for the resident perception/prompt path  
**Scope:** source-level trace, frozen-ledger verification, and implementation sequence; no live-agent experiment

## Decision and current state

The baseline resident was not sent an LLM narration every cognitive tick. It polled a broad sensory surface
every 20 seconds, reduced that input into ledger-derived state, and called the resident model only when
surprise ignited or an idle settling/fervor interval fired. The practical failure was subtler: rolling chat
and recent-event windows remained prompt-eligible across ticks; speech could appear both as chat and as a
world event; and idle pulses inherited reactive situation bundles. Slices 1–5 now provide exact prompt
traces, consume-once encounters, mode-selected context, private typed reaches, and structured source
records. The remaining direction is a richer bounded sensorium and elective ecosystem—especially physical
plural sources—followed by prompt-diet cleanup and removal of the residual action narrator.

## A. Captured baseline production trace

This section records the production path as it stood when the monoculture diagnosis began on 2026-07-14.
It is evidence for the decisions below, not a claim that every named defect remains after the implemented
slices in Section E.

### Process lifetime

- `Resident.run()` starts one `CognitiveCore`, a runtime mirror, and growth-proposal sync. The deleted
  fast/slow/mail/wander schedulers do not run.
- `CognitiveCore.run()` calls `tick_once()` and then sleeps 20 seconds. It does this continuously, including
  at night. Circadian wakefulness scales arousal; it does not currently suspend perception or create a true
  sleep interval.
- Startup staggering changes only when resident tasks begin. It does not change their later cadence.

### Every cognitive tick: reads, but normally no model call

`perceive()` currently reads:

1. `GET /api/world/scene/{session_id}`: location, co-presence, up to ten recent local world events, ambient
   presence, and the location graph. `CityWorld` also appends a synthetic recent event advertising every
   available tool.
2. `GET /api/world/grounding`: local time and weather, reduced into circadian/rest and vigilance pressure.
3. `GET /api/world/location/{location}/chat?limit=30`: the latest thirty local lines. No cursor is passed.
4. `GET /api/world/location/__city__/chat?limit=30`: the latest thirty citywide lines, from which perception
   randomly samples one while parked or three after movement. Incubation can temporarily close this seam.
5. `GET /api/world/dm/inbox/{agent}`: unread mail, which the server marks read when fetched.

The tick writes/reduces sensor evidence and builds a transient perception brief:

- location and co-present names;
- the last five recent-event summaries;
- the last six heard lines;
- unread-mail count;
- time/circadian grounding;
- reachable adjacent locations;
- workshop summary, recent makings, and anchors extracted from the last ten felt senses plus perceived names.

Chat packet insertion is deduplicated in the ledger, but inclusion in the transient brief is not. A line
returned by the rolling HTTP window may therefore be shown to more than one later pulse even though it was
only recorded as a new packet once.

### When the resident model is called

The integrator calls the resident LLM only in one of these modes:

- **react:** leaky surprise/arousal crosses `1.0` (normally with a 30-second refractory interval);
- **settling:** arousal has remained at or below `0.3` for five minutes;
- **fervor:** arousal has remained at or above `0.45`, but below ignition, for three minutes;
- **venture:** a specialization of fervor when the action-tendency flag is enabled;
- **forced ignition:** a callable/testing seam; the production resident loop does not currently pass it.

No ignition and no idle condition means no LLM request on that tick.

### The resident LLM request

The system message is:

- the full composed resident soul;
- the standing factual `GROUND TRUTH` briefing;
- optionally, when enabled, resident-specific voice samples.

The user message is one centrally assembled prose document containing, depending on mode:

- mode opener, time, location, co-presence, and recent local world-event summaries;
- up to four heard lines, including the sampled citywide line;
- inbox count and adjacent movement targets;
- recent-act groove, relevant/recency memory, and workshop history/instructions;
- settled baseline, current anchors, current cognitive-node activations;
- prediction/afterimage and numerical surprise traces for reactive/fervor/venture modes;
- an identity-resonant soul fragment for reactive mode;
- the JSON pulse contract and one deterministic worked example.

The model returns one typed JSON pulse: felt sense, zero or one act, predictions, optional drive nudges,
self-delta, trace verdicts, and keepsakes.

### Acts and the second narration seam

- `speak` writes local chat, an explicit city broadcast, or a private directed carry. Chat itself is stored
  without narration, but it is also copied into world history as an utterance event.
- `move` uses the deterministic map movement endpoint.
- `write` writes the private workshop or directed mail.
- `do` calls `post_action`. A `do` whose body is `use <tool> ...` is intercepted by `CityWorld`; its result
  is returned directly. Other `do` acts enter the engine's still-live staged action pipeline, whose separate
  narrator model receives a JSON context object and produces narrative plus a public summary.

Every `do` result is handed back to the resident model in a tool-continuation prompt. The resident may make
up to six further `do` calls within that ignition, then speak/write/move or stop. This is the only path on
which the world narrator directly talks back to the resident as the result of its own chosen action. It is
not an every-tick narrator.

The engine's public summary becomes a local world event and can appear in later residents' `Recently here`
blocks. Local speech can appear twice in a pulse: as `Name said: ...` in recent events and as the original
line under `What you can hear nearby`.

## B. What the frozen run proves

The source trace is corroborated by `shards/ww_sfo/residents/silva_costa/memory/runtime_ledger.jsonl`.
In the 2026-06-07 segment around 05:47-05:52 UTC:

- grounding and ambient pressure were appended approximately every 20 seconds;
- infrastructure-heavy city lines were repeatedly sampled from the rolling city feed;
- at 05:49 an idle pulse fired and answered Hiroshi's most recent sampled line;
- the response stored a new keepsake about salt, fog, and marine risers and cast `fog` and `salt` as anchor
  predictions;
- later ticks continued to sample substrate, torque, masonry, transformer, and hardware-failure lines.

That one exchange shows the complete regenerative path:

```text
saturated city feed
  -> content-blind sample
  -> transient prompt context
  -> resident answer
  -> public speech/world event
  -> kept memory + felt sense + anchor prediction
  -> relevance recall/anchor prompt on later pulses
  -> another answer on the same semantic ground
```

Content-blind sampling prevents a designer from targeting a resident's beliefs, but it cannot manufacture
diversity from a saturated source. Once the shared subject is also stored as the resident's own memory and
prediction, reducing broadcast volume alone does not remove it.

## C. Baseline monoculture mechanisms to treat as separate causes

1. **Source saturation.** A random sample from a monotopic city channel is monotopic.
2. **Rolling-window replay.** Local and city chat are fetched without cursors. Ledger dedup does not prevent
   transient prompt replay.
3. **Representation duplication.** Speech is both chat and a world-history utterance; actions are both actor
   text and narrator public summaries.
4. **Self-reinforcing retrieval.** The current moment selects relevant memories; shared-topic memories make
   the next response more shared-topic. Felt senses generate anchors, and anchors are explicitly shown back.
5. **Idle-prompt contradiction.** Settling says that nothing presses and no one waits, but still includes the
   rolling heard/recent-event bundle. A resident can answer the commons during what is nominally inward rest.
6. **Common cognitive vocabulary.** Every resident is repeatedly shown the same language of traces,
   afterimages, prediction, anchors, slipping, grooves, and world mechanisms. This is not proven as the root
   cause, but it is a plausible shared semantic prior and should be removed from phenomenological prompt prose
   where the mechanism does not require it.
7. **Worked-example priming.** The common example pool includes a rusted latch that has needed fixing. Stable
   per-resident selection distributes the examples, but each example still supplies authored subject matter.
8. **Thin elective surface.** `eats`, `recall`, `news`, `places`, `investigate`, and `chatter` already form a
   primitive elective ecosystem, but they are advertised as synthetic recent events and invoked through the
   overloaded physical `do` act. Their results are narrative strings, not source records.
9. **Attractor-preserving choice.** Blank `chatter` is ranked by soul resonance. This can deepen distinction
   when the source is plural, but can reinforce an existing attractor when the soul, memories, and source have
   already converged.
10. **Historical carryover.** Existing ledgers, keepsakes, workshops, and growth material can regenerate the
    old topic after transport changes. Architectural validation must distinguish new encounter input from old
    self-history instead of treating a reset as the only remedy.

## D. Target architecture

### 1. A bounded unavoidable sensorium

Push only what embodiment makes unavoidable:

- current place and co-presence;
- genuinely new local speech and direct address;
- material local world changes;
- circadian/body state;
- path-local encounters and physical traces met during traversal.

This layer is local, source-attributed, consume-once where appropriate, and small. It does not include a
rolling global narration or a global random line merely because another 20 seconds elapsed.

### 2. Elective epistemic actions

Information acquisition becomes a first-class resident choice distinct from a physical world act. A pulse
may choose to inspect a source, follow a person/thread, search a question, browse without a query, or recall
its own material. The result can enrich private cognition without requiring immediate public speech.

The existing in-ignition continuation loop is the right orchestration seam. Do not add another scheduler.
Split its overloaded `do` path into typed epistemic/tool calls and physical acts.

### 3. Source records, not narrator paragraphs

Each information provider returns records with at least:

- stable record/source ID;
- provenance class (self-memory, local observation, world record, private correspondence, external egress);
- observed/created time and freshness;
- locality and visibility;
- original author/actor where relevant;
- structured payload plus a deterministic local rendering.

The resident chooses a source/query. The runtime renders selected records into prompt context. No hidden
narrator should invent connective prose between unrelated records.

### 4. Persistent questions and attention commitments

The pulse may leave an open question, followed source, or person/thread subscription in the ledger. Those
commitments create future opportunities to look again without making a city feed ambient. They are resident
state, not population recommendation targets.

### 5. A physical, stigmergic commons

Major 65's trace commons is the strongest unchosen source: residents leave marks on world objects/places;
others encounter them locally and later. It provides shared history through the world rather than through a
feed. Traces need locality, provenance, visibility, and decay/renewal semantics.

### 6. Choice without a recommender trap

Elective does not mean silently soul-ranked by default. Every plural source should support:

- explicit query;
- explicit named source/person/thread;
- chronological or content-blind browse.

Soul resonance may be an overt resident-side focusing mode, not the only invisible ranking rule. Preserve a
small unchosen floor through embodiment and traversal, never through content-targeted contrarian sampling.

## E. Implementation sequence

### Slice 1 — exact prompt observability, behavior unchanged

**Implemented 2026-07-14 (`fe997e6`).** Exact private prompt/completion traces now exist outside the
cognitive ledger.

- Persist a private append-only trace for every resident-model request: exact system/user messages, mode,
  model parameters, input context, source IDs available today, image digests, raw completion, and failure.
- Keep it outside substrate reducers so observing a prompt cannot change cognition.
- Add a small reader/debug command later; first make the evidence exist.

### Slice 2 — encounter identity and consume-once semantics

**Implemented 2026-07-14.** Engine scene records now expose stable event identity/type; chat packets carry
source and encounter IDs, persist through non-prompt ticks, and become observed only after prompt
inclusion. `utterance` world events are removed at the context boundary when chat already carries the
speech. City overhears retain a bounded pending set and never resample an already-known line. Source
advertising is now a typed affordance rather than a synthetic recent event.

- Add cursors/stable IDs to local chat and scene-event perception.
- Carry IDs into the transient brief and record which items were selected for the prompt.
- Deduplicate chat versus utterance-event representations at the context boundary.
- Stop using a synthetic recent event to advertise sources.

### Slice 3 — a typed context envelope before prose rendering

**Implemented 2026-07-14.** `PulseContext` retains provenance and records available, selected, and withheld
sources. Mode policy selects before affect, recall, rendering, tracing, and packet consumption, keeping all
five views aligned. Self-directed settling/fervor/venture pulses withhold rolling chat, recent events, and
inbox counts while retaining location, co-presence, navigation, time of day, and concrete affordances.

- Replace ad hoc prompt concatenation with a `PulseContext`/`PromptEnvelope` whose sections retain source
  provenance.
- Give each mode an explicit context policy. Settling should not inherit rolling social material unless a
  direct, new encounter actually caused it.
- Render the envelope to prose only at the final inference boundary.

### Slice 4 — typed elective information calls

**Implemented 2026-07-14.** A pulse now has a typed, private `reach` (`inspect`, `read`, or `attend`) that
is mutually exclusive with outward `act`. The bounded within-ignition continuation can reach repeatedly,
then act once or end with no outward act. City knowledge sources and familiar scoped-file reading resolve
through `InformationAccess`; known legacy `do: use ...` / `do: read ...` forms are declined rather than
sent through the action narrator. Every access attempt is durable ledger evidence without becoming a
world action.

- Separate `inspect/read/attend` reaches from physical `do` acts.
- Let a result end in a null outward act while still being recorded as privately learned/encountered.
- Preserve the single cognitive core and the bounded in-ignition continuation loop.

### Slice 5 — source registry and migration of existing tools

**Implemented 2026-07-14.** The city now exposes a named `CitySourceRegistry`; `eats`, `recall`, `news`,
`places`, `investigate`, and `chatter` return structured records instead of provider-authored response
prose. Familiar file reads use the same record shape. Record identity, provenance, freshness, locality,
visibility, and selection mode survive provider -> private ledger evidence -> reach continuation trace;
only the inference-boundary renderer converts them to text. Chatter now makes `named_peer`,
`chronological`, `soul_resonance`, and `query_plus_soul_resonance` selection legible.

- Define one provider contract and migrate `recall`, `news`, `places`, `investigate`, and `chatter`.
- Return source records instead of precomposed narrative strings.
- Expose provenance, freshness, locality, visibility, and selection mode in prompt traces.

#### Correction: the registry belongs to the resident/world seam, not the city

Major 86 establishes one continuous resident with hearth and city embodiments. The current
`CitySourceRegistry` and hand-coded familiar `files` source prove the provider shape but leave it in two
composition roots. Before adding the seed kit, extract a shared registry/provider contract:

- resident-scoped faculties travel with the resident;
- HearthWorld and CityWorld contribute only their current world-scoped sources;
- keeper/FileScope/MCP grants are optional hearth capabilities, not universal resident facts;
- changing world attachment rebuilds the world-scoped catalog so city sources cannot leak into the hearth;
- FileScope uses an authorized-reading provenance class and is rendered as deliberate reading, never as
  already-held knowledge.

**Foundation implemented 2026-07-14:** the generic registry/provider contract now lives in
`runtime/information.py`; CitySourceRegistry extends it only for city drive binding; LocalWorld contributes
FileScope through it. `scoped-reading` and `self-memory` survive advertisement, structured records, ledger
evidence, prompt trace, and the reach-continuation instruction. Recall is now constructed as a
resident-scoped provider and composed into both city and hearth catalogs.

### Slice 6 — physical plural sources

**In progress 2026-07-14.** Major 65 Layer 1 is implemented end to end: a dedicated expiring,
location-bound store; narrator-free `mark` acts; and bounded, source-attributed, consume-on-prompt physical
encounters. The broader Slice 6 work—world-object reading and additional independent physical sources—remains.

- Implement Major 65's local trace commons and world-object reading.
- Replace the parked global-overhear surrogate with local/path encounters once the world supplies enough
  unchosen material.
- Continue Major 64 as independent world sources competing in state, not as more prose injected into every
  prompt.

### Slice 7 — prompt diet cleanup

- Remove shared worked-example subject matter in favor of schema validation or content-free examples.
- Translate mechanism terms into minimal phenomenological language; keep numerical diagnostics in the trace,
  not in the resident's prose unless they are cognitively necessary.
- Stop feeding unchanged workshop, memory, recent-event, and anchor blocks by default. Include them by
  context policy and source selection.

### Slice 8 — delete the residual action narrator with Major 69

- Finish the lean interpret/validate/reduce/submit action path.
- Delete `turn_service.py` and `src/services/turn/` only after their remaining validation/interpretation
  ownership has a clear home.
- Physical actions should return receipts and observable state changes. Resident interpretation belongs in
  resident cognition; public projection should be deterministic where possible, not a second LLM's prose
  fed back into the population.

## F. Non-live validation gates

These architectural slices do not require another faulty-machinery population run to establish correctness:

- a silent tick makes no inference request;
- every inference request has an exact private trace and source manifest;
- the same chat/event ID is not injected twice or on multiple pulses without an explicit re-read;
- local speech is not simultaneously rendered as heard chat and recent-event narration;
- settling receives no stale social bundle;
- an elective read may end without speech/action;
- source records remain private unless a later pulse chooses to externalize them;
- source provenance survives provider -> ledger/trace -> prompt;
- citywide information appears only after an explicit choice, except for a bounded, content-blind embodied
  encounter floor;
- prompt/context snapshot tests expose changes to shared semantic primers.

## Relationship to active work items

- **Major 60:** partially realizes the target (chosen `chatter` plus an unchosen floor). Chatter now returns
  structured records with explicit selection modes, but source saturation and soul-ranked attractors remain
  architectural risks.
- **Majors 63 and 72:** physical speech/private carry are substantially present in code even where work-item
  status text is stale; formal source/visibility records remain.
- **Major 64:** supplies plural world sources; do not implement it as a larger prompt bundle.
- **Major 65:** is the constructive center of the target architecture, especially the trace commons.
- **Major 86:** owns resident continuity across hearth/city worlds and therefore the placement/lifetime of
  every elective source and outward capability.
- **Major 66:** stable encounter and source IDs have landed on the prompt path; relational reply/edge identity
  remains the larger ledger task.
- **Major 69:** removes the residual engine narrator and turn-pipeline feedback seam after the event spine is
  stable.
- **Major 85:** prompt traces and source history strengthen the case for truly append-only, non-truncating
  resident evidence, but prompt diagnostics must remain outside cognition reducers.
