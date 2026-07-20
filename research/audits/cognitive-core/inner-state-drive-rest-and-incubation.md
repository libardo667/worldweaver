# Inner state, drive, rest, and incubation

Status: code audit completed 2026-07-19. This document describes the live implementation. It does not infer
what a resident experiences from variable names or generated prose.

## Plain-language result

This part of CognitiveCore does not currently model a body, emotion, grief, sleep, or a self forming in
solitude.

It implements several narrower policies:

- an embedding model finds text that is similar to the host-authored identity prompt;
- that similarity selects an identity sentence for the next prompt, ranks some public chat, ranks possible
  destinations, and optionally decides which extracted words can affect call timing;
- repeated observations that one predicted word is absent add an extra term to call pressure;
- a fixed curve based on the city clock makes model calls less likely at night;
- an optional new-resident gate hides citywide chat and silently saves attempted speech as private writing;
- another embedding comparison tells a resident that a repeated topic has lost its pleasure.

Some of these may be useful experiments. Their current names and explanations make much stronger claims than
the code supports. More seriously, the policies can reinforce the very semantic monoculture they were meant
to prevent.

## The live loop

```text
host-written canonical soul + adopted growth
                    |
                    v
           embedding similarity
             /      |       \
            /       |        \
prompt identity quote   chat ranking   destination ranking
            \       |        /
             \      |       /
               later model output
                       |
              public speech / making
                       |
        more text resembling the existing identity
```

This is not automatically a bad loop. Stable interests require some continuity. But it is a recommender loop
around an identity that the host and seed model largely wrote before the resident's first call. It can preserve
a stereotype as easily as it can preserve individuality.

## 1. `DriveVector` is semantic retrieval, not affect

### What it computes

`DriveVector.build()` splits identity prose into fragments and embeds them. `resonance(moment)` embeds the
current text, calculates cosine similarity to every fragment, multiplies the score by a fixed slice weight,
and returns the highest positive matches.

The advertised slices are:

| Slice | Fixed weight | Live source |
| --- | ---: | --- |
| constitution | 1.0 | canonical soul |
| growth | 0.55 | adopted growth soul |
| reverie | 0.35 | none in the production builder |

The production call in `CognitiveCore._ensure_drive_vector()` supplies constitution and growth only. The
claimed reverie component is empty.

The result is a non-negative topical-similarity score. It has no positive-versus-negative emotional valence,
no pleasure or aversion, no bodily signal, and no learned preference based on consequences. Calling it
“affect,” “what stirs you,” “the resident's own nature,” or “gravity” does not make those properties appear.

There is a `valence_fn` seam in the salience integrator, but `CognitiveCore` never supplies it. Live surprise
records therefore use the default neutral value, `0.0`. The drive vector does not supply surprise valence.

### What it changes

The same score has several live effects:

1. **Reactive prompt steering.** The prompt quotes the most similar identity fragment and says, “Answer from
   that.”
2. **Public-chat selection.** An elective blank or topic `chatter` read considers the latest 14 citywide
   messages and returns the four most similar to the resident's identity. A name query uses a separate
   substring match.
3. **Destination selection.** An optional venture mode ranks reachable place names by identity similarity.
   The default chooses the maximum; an environment flag can instead sample from the scores.
4. **Anchor admission.** When optional anchor gating is enabled, only extracted tags with similarity at or
   above `0.5` may enter the surprise field.
5. **Identity-change gating.** `contradiction_check()` calls a proposed growth item contradictory when its
   topical similarity to the canonical soul is below `0.12`. The code itself admits that it does not detect
   opposition.

The memory retriever uses the same embedder but is a separate relevance operation over selected notes.

### Why this can narrow a resident

The seed process can assign a livelihood, upbringing, temperament, and social style, then freeze model-written
prose about them into the canonical soul. The drive path can then:

- show the resident the most seed-compatible sentence at a live moment;
- select seed-compatible city speech;
- prefer a seed-compatible destination;
- reject later growth that is merely topically distant from the seed.

That is a plausible positive-feedback path from initial casting to semantic concentration. It is not proof
that this mechanism caused the observed monoculture; it is a concrete, testable alternative to the source
comment's unsupported claim that it makes twelve same-room models respond as twelve people.

### Provider and privacy dependence

When configured, the embedding endpoint receives identity fragments, moment text, selected memory text,
public-chat bodies, place names, and anchor tags. The endpoint may be local, but `RemoteEmbedder` accepts any
OpenAI-compatible URL. “Local-first” comments elsewhere do not guarantee that these inputs stay on the
machine.

The provider also changes policy:

- without embeddings, chat falls back to recency, destination selection falls back to the first place, the
  anti-repetition warning disappears, relevance memory falls back, and anchor gating stays closed;
- with embeddings, all of those behaviors become model-dependent;
- `_drive_built` is set before the first build attempt, so one temporary build failure disables drive until
  process restart or adopted identity growth triggers a rebuild;
- `MemoryRecall` is installed before that failure and may continue trying the failed endpoint during later
  activations.

Provider availability is therefore not just an optimization detail. It silently selects a cognitive-policy
arm and creates a potentially sensitive data-egress surface.

## 2. Anchors mix public presence with claimed inner fixation

`CognitiveCore` builds up to eight anchors from:

- article-headed noun phrases in the last ten `felt_sense_logged` model self-reports;
- names of residents currently present;
- actors named in recent public events; and
- speakers in the currently heard packet set.

Structured names count twice. Scores are normalized to the most frequent current candidate. This means one
person who has just entered the room can immediately become an anchor with salience `1.0`, without prior
attention or recurrence.

The prompt then calls these mixed inputs “the concrete things your attention keeps returning to” and “the
anchors of your inner world.” That is false provenance. Some are current public inputs selected by the host,
not repeated resident attention. The code comment recognizes the problem and hides anchors from non-reactive
prompts, but it still mislabels them inside reactive prompts.

Other lifecycle problems remain:

- the ten self-reports have no wall-time window, so old prose remains until ten later model calls displace it;
- individual anchors do not retain their source or event ID;
- `record_anchors()` refuses an empty list, so it cannot write an explicit empty-current snapshot;
- optional gating labels cosine similarity “mattering” and treats `0.5` as “the price on boring” without
  evidence from resident choice;
- an embedding cosine of `0.65` can rename a currently extracted phrase to a predicted phrase, making model
  provider output part of the apparent identity of the object.

An extractor is useful. The current output should be called something like `recent_entity_and_phrase_tags`
until provenance and resident endorsement justify a stronger term.

## 3. `grief` counts missing-tag observations, not loss

### What the code requires

The mechanism runs only when optional anchor gating produced a non-empty current anchor field. For each
strongly predicted anchor tag missing from that field, the tick records an absence item. `derive_grief()` then:

1. ignores a tag unless a previous surprise event recorded that exact tag as present;
2. sums all later absence observations for it;
3. decays each observation with a ten-minute half-life;
4. drops totals below `0.25`; and
5. adds half the sum to call pressure, capped at `0.8`.

This does not establish that a person, object, or relationship was lost. A missing tag can result from:

- a person leaving the newest packet set;
- the top-eight extraction limit;
- an article-phrase mismatch;
- the source withholding an event;
- an embedding-model alignment choice;
- a current field containing other gated tags but not this one; or
- repeated polling of an unchanged scene.

Presence is also only recognized inside this optional surprise path. General world presence does not count.

### Polling-rate reproduction

A deterministic fixture used the same predicted anchor, the same earlier presence, the same final ten-minute
interval, and the same absence throughout. The only change was how many polls recorded that absence:

```text
one absence observation:
  grief = {"the cup": 1.0}
  grief contribution to call pressure = 0.5

ten absence observations:
  grief = {"the cup": 7.4664}
  grief contribution to call pressure = 0.8 (capped)
```

The raw value measures a decaying count of polls. It does not measure duration of absence, evidence confidence,
relationship, importance, resident appraisal, or grief. Because the capped term survives model calls, it can
make the next small surprise cross the call threshold. This is behavior-changing scheduler state, not harmless
telemetry.

Terms such as “confirmed absence,” “organ for loss,” “raw,” and “below that it is not yet felt” are unsupported.
Retain the append-only evidence if useful, but remove it from call pressure until absence has world-backed
identity, provenance, elapsed-time normalization, and an explicit evaluation.

## 4. The circadian curve is a clock-based call throttle

### What it computes

The code uses one cosine with:

- a fixed subjective peak at 15:30;
- a trough twelve hours later;
- a wakefulness floor of `0.25`;
- a fixed exponent of `1.4` for the inverse curve; and
- a phase offset of at most three hours, currently derived from a hash of the resident folder name unless an
  explicit numeric override is passed.

Those constants are not calibrated to resident observations or a declared simulation population. The doula's
categorical birth-time chronotype and the identity tuning chronotype are not connected to this live function.

Perception maps the city's clock directly to `wakefulness`, `rest_pressure`, a `fatigue` signal, and a phase
label. Wakefulness multiplies call pressure. Late-night values therefore make ambient input less likely to open
a model call.

### What it leaves out

Sleep research commonly distinguishes circadian timing from a homeostatic process that depends on sleep/wake
history. The two-process model is not the only possible account, and newer work examines interactions between
the two, but both make the missing distinction clear: a fixed inverse of the same clock curve is not evidence
of accumulated sleep pressure. See Borbély et al.'s
[reappraisal of the two-process model](https://doi.org/10.1111/jsr.12371) and Franken and Dijk's
[review of sleep and circadian homeostasis](https://doi.org/10.1038/s41583-023-00764-z).

WorldWeaver has no durable sleep/wake state, time-awake debt, recovery from sleep, activity cost, metabolism,
or resident decision to sleep. The game rules can also explicitly disable survival needs and injury.

The current mechanism may still be a useful and cheap city-cadence policy. It should be described as that. It
does not warrant comments that the resident “feels” night or has a realistic chronotype.

## 5. `resting` means “do not call the LLM on this tick”

When no reactive call is due, `derive_rest()` uses the latest logged wakefulness, current call pressure, and
five quiet minutes. If wakefulness is at most `0.35` and effective pressure is below `0.3`, the integrator
returns before settling, fervor, venture, and the model call.

The process is still awake in the operational sense:

- the tick loop continues;
- it polls the city scene, local chat, mail, weather, and clock first;
- it writes perception and derived evidence;
- a direct address or enough pressure opens a call immediately; and
- no sleep start or wake event is stored.

That is a quiet scheduler state, not sleep. It may be exactly the right host behavior, but calling it bodily
rest makes later reasoning and testing muddy.

There is also a stale-state hazard. If a grounding request fails after a prior low-wake observation, the
current perception brief defaults reactivity to `1.0`, while `derive_rest()` can still read the old low-wake
observation from the ledger. Different parts of the same tick can therefore use different clock states until
a later successful poll.

## 6. The runtime has no interoception in the ordinary scientific sense

A major interoception review defines the subject around sensing, interpreting, and integrating signals that
originate within the body: Khalsa et al.,
[“Interoception and Mental Health: A Roadmap”](https://doi.org/10.1016/j.bpsc.2017.12.004).

The live WorldWeaver values originate from:

- an external city clock;
- public and private message counts;
- movement and event records;
- model-authored prose; and
- fixed arithmetic over those records.

There is no simulated internal physiological condition being sensed. The `CityWorld` and effector do provide a
valuable functional attachment to location, permission, co-presence, and consequences. Calling that a
software body is a defensible project metaphor if clearly qualified. Calling the clock curve interoception or
homeostasis is not.

This does not mean WorldWeaver should imitate human organs. It means any proposed internal condition must be
specified as game state or scheduler state and evaluated on its own terms.

## 7. Incubation is covert speech redirection

Incubation is optional and currently off by default in identity tuning. When enabled for a city resident, it
lasts at least four minutes and at most fifteen, unless five qualifying events lift it between those bounds.

The source says a cold arrival has “nothing of its own to resist the current,” that private making builds a
self, and that the policy changes only when the resident meets the city. The implementation does something
different:

- “arrival” is the earliest timestamp anywhere in the resident ledger, not arrival in this city or process
  start. A resident with an older hearth ledger skips the gate in a new city;
- citywide elective `chatter` is hidden, but exact-place incoming speech still reaches the resident;
- every attempted `speak` action is intercepted before normal target routing;
- the text is appended to the private workshop as a journal entry;
- the action result says `executed=True`, `kind=speak`, and `incubated=True`, although no speech occurred;
- that workshop event counts toward the five-event release threshold;
- the resident is not warned in the ordinary action prompt that speech will be rewritten;
- the current action-feedback bug can prevent the model from learning promptly that nobody heard it.

This includes a direct reply to a co-present person and speech addressed to somebody elsewhere. Exact-place
speech can reach the new resident, but the new resident cannot answer in kind.

The gate therefore rewards producing attempted speech: five attempts can satisfy the code's measure of “a self
being built,” while quiet waiting cannot lift it before the maximum time. The mechanism systematically favors
output over silence even though its documentation denies output steering.

The tests confirm the redirection as intended behavior. They protect the policy from accidental change; they
do not validate the claims about selfhood, individuality, or lawfulness.

If a game needs delayed access to a citywide channel, say that plainly in the shard rules and user-facing
affordances. Do not convert one intended act into another or call event count selfhood. For the general runtime,
retire this path rather than tune it.

## 8. `self_sameness` is an anti-repetition command

When at least four recent makings exist and an embedder is available, the runtime embeds them, takes the latest
item's cosine similarity to the centroid of the earlier items, and clips negative values to zero. At `0.80` or
higher, the prompt tells the resident:

- its work has “worn a groove”;
- “that pattern's pleasure is spent”; and
- it must make something genuinely different or stop.

Semantic similarity does not observe pleasure, boredom, compulsion, craft development, or the resident's
evaluation of repetition. The instruction makes repeated study, revision, ritual, style, and practice suspect
by default. It also disappears when the embedding provider is unavailable.

If output concentration is a research measure, keep it in content-blind or privacy-preserving offline analysis.
Do not feed a verdict about pleasure back into the resident unless the resident supplied that verdict.

## What is worth keeping

Several engineering seams are useful once stripped of false interpretation:

- optional embeddings behind a clear provider and privacy declaration;
- typed source results that report how records were selected;
- chronological and named-peer alternatives to semantic chat ranking;
- a configurable city-local day/night cadence;
- an explicit no-call path that permits quiet;
- provenance-rich extraction of recent entities as an experimental feature;
- hard host call, time, and cost limits stated as resource limits; and
- isolated metrics for semantic concentration that do not prescribe resident behavior.

## Required repairs before another mechanism claim

1. Rename `DriveVector` as identity-conditioned semantic retrieval in public and internal descriptions.
2. Separate its four policy roles. Prompt retrieval, chat ranking, place selection, and identity-change review
   must be independently switchable and testable.
3. Record embedding provider, model, prompt/content class, privacy boundary, failures, and fallback arm without
   logging private text.
4. Add chronological, explicit-query, diversity-aware, and unranked controls for public chat and place choice.
5. Remove cosine-as-contradiction from the identity authority path.
6. Give extracted tags per-item provenance and explicit empty snapshots; do not call public names inner
   anchors.
7. Remove `grief` from call pressure until absence refers to a durable world entity and is normalized by
   elapsed time rather than polls. Rename stored evidence literally.
8. Keep the clock curve only as an optional cadence policy. Remove claims of sleep, felt fatigue,
   interoception, homeostasis, and realistic chronotype.
9. Retire covert incubation speech redirection. A shard-specific channel delay must be visible and must never
   translate an intended reply into private writing.
10. Remove the “pleasure is spent” instruction. Measure semantic concentration outside the prompt first.

## Paired tests

| Question | Control | Treatment | Structural measure |
| --- | --- | --- | --- |
| Does identity retrieval support continuity? | no identity quote | top similar identity quote | correct use of seeded stable facts; cross-resident convergence; topic concentration |
| Does resonance narrow public attention? | newest four city messages | top four identity-similar messages | speaker/topic coverage; repeated-record rate; later voluntary source diversity |
| Does destination ranking create homophily? | unranked choice surface | max similarity; sampled similarity separately | location concentration; encounter network; repeated blocked movement |
| Do anchors add causal value? | no extracted tags | provenance-separated tags | false absence, false call, persistence after source removal |
| Does the clock curve help shared cadence? | fixed call pressure | explicit clock multiplier | latency to addressed input, overnight calls, cost; no personality score |
| Does a visible channel delay help cold starts? | full affordances | citywide channel unavailable, no speech rewrite | attempted unavailable actions, direct-reply delivery, later source diversity |
| Does self-sameness feedback help? | measurement only | current anti-repetition prompt | resident-selected revisions, topic diversity, stopped work; no assumption that novelty is better |

No test should score talkativeness, movement, novelty, or visible production as health.
