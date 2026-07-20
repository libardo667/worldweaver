# Evidence review 03: clock cadence, sleep, interoception, and semantic policy

Status: bounded review, 2026-07-19. This review asks what outside work can and cannot establish about four
live implementation claims: clock-derived rest pressure, bodily/interoceptive language, semantic similarity
called affect, and isolation called self-building.

It does not ask whether an LLM sleeps, feels, has a body, or has a self. Current behavioral traces cannot
answer those questions.

## Search record

Date: 2026-07-19.

Queries:

- `Two-process model sleep regulation Borbely 2016 DOI`
- `sleep homeostasis circadian process time awake sleep review 2024`
- `Interoception and Mental Health A Roadmap Khalsa DOI`
- exact-title and PubMed follow-ups for publication and DOI verification

Source roles were kept separate. Sleep reviews describe biological evidence and models; an interoception
consensus review defines a research construct and its measurement problems. Neither directly validates or
invalidates a software scheduling policy.

## Circadian timing is not the same variable as sleep pressure

Borbély and colleagues' reappraisal describes a homeostatic Process S interacting with a circadian Process C:
[“The two-process model of sleep regulation: a reappraisal”](https://doi.org/10.1111/jsr.12371), 2016.
The review reports wide use of that framework while also discussing physiological interaction and processes
that complicate a simple separation.

Franken and Dijk more recently review evidence that sleep and circadian rhythmicity are intertwined rather
than fully independent:
[“Sleep and circadian rhythmicity as entangled processes serving homeostasis”](https://doi.org/10.1038/s41583-023-00764-z),
2024.

These sources do not require WorldWeaver to implement a human sleep model. They do show why its current names
are misleading. `rest_pressure` is just an exponentiated inverse of the same clock cosine that produces
`wakefulness`. It has no independent history of time awake or asleep, and the resident never enters a durable
sleep state.

Decision: keep a clock curve only if it improves a declared scheduling goal. Call it a city-time call
multiplier or night cadence, not sleep homeostasis, fatigue, or felt rest. Compare it with no multiplier and
with resident-controlled schedules.

## Interoception requires an internal bodily signal

Khalsa and colleagues describe interoception as nervous-system sensing, interpretation, and integration of
signals originating within the body, while emphasizing unresolved conceptual and measurement problems:
[“Interoception and Mental Health: A Roadmap”](https://doi.org/10.1016/j.bpsc.2017.12.004), 2018.

WorldWeaver's current clock, message counts, public events, movement records, and model prose do not originate
inside a simulated physiological system. A variable being hidden from other residents is not enough to make it
interoceptive. A numeric signal being inserted in a self-oriented node is not enough either.

Decision: do not call the current substrate interoceptive. Preserve “body” only as a clearly qualified
functional term for the typed world attachment. If a game later adds hunger, injury, exertion, or sleep state,
those are still simulated state variables whose meaning must be stated directly; biological analogy would
remain a separate claim.

## Cosine similarity is not evidence of affect

No outside source is needed to establish the immediate mismatch. The function computes normalized-vector dot
products over text embeddings. It returns the largest positive topical alignments and has no observed
pleasantness, unpleasantness, bodily activation, appraisal, learned reward, or resident judgment.

External affect literature cannot donate those missing inputs to the implementation. Even a theory in which
meaning and affect interact would not turn every semantic similarity score into affect.

Decision: classify this as identity-conditioned semantic retrieval. Test each use independently. In
particular, compare public-chat ranking and destination ranking against chronological, query-only, unranked,
and diversity-aware controls before claiming that the filter preserves individuality.

## Solitary output count is not evidence that a self formed

The incubation claim is not supported by the program's measure. Its `groundedness` count consists only of
selected-memory and workshop events. A redirected speech attempt becomes a workshop event and therefore helps
lift the gate. Quiet reflection with no recorded output does not.

Human developmental, social, contemplative, or isolation research cannot be transferred directly to this LLM
runtime. More importantly, none is necessary to identify the software contradiction: the implementation says
it does not steer output while it rewards output, rewrites intended speech, and labels the result self-building.

Decision: remove covert speech redirection from the general runtime. If a game shard wants a delayed citywide
channel, disclose it as a rule, preserve exact intended action and failure feedback, and test it as an exposure
policy rather than a theory of selfhood.

## Decisions supported by this review

- Treat clock-dependent quiet as a scheduler policy, not a biological model.
- Do not use `sleep`, `homeostasis`, `fatigue`, `felt rest`, or `interoception` for the current data path.
- Treat embedding similarity as retrieval/ranking, not affect, motivation, contradiction, caring, or pleasure.
- Treat semantic concentration as a measurement question before feeding it back as an anti-repetition order.
- Remove or visibly isolate policies that translate one resident act into another.
- Do not seek scientific authority for a desired personality. Run direct software comparisons and preserve
  silence, repetition, withdrawal, social contact, and novelty as possible outcomes rather than scores.
