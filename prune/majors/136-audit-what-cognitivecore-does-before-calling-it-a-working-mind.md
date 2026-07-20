# Audit what CognitiveCore does before calling it a working mind

## Problem

WorldWeaver can now run residents, bound model-call chains, preserve private history, notice nearby events,
and carry typed actions into a world. None of that proves that `CognitiveCore` is a good account of mind,
agency, attention, memory, embodiment, or a resident's relation to its surroundings.

Recent fixes have been driven by visible problems: repetitive conversation, slow replies, excessive reading,
missed co-presence, and high inference cost. Those are useful observations, but they can smuggle in an
unexamined ideal resident: social, active, responsive, cheap, and easy for a human to read. A person may
reasonably spend a day reading, avoid conversation, act slowly, change interests, or sit with no visible
output. The runtime must not label those choices broken merely because they are inconvenient to observe.

The code also borrows terms such as perception, arousal, surprise, salience, prediction, ignition, memory,
felt sense, and drive. Some are implementation names, some refer loosely to scientific ideas, and some may
sound stronger than the mechanism warrants. We do not yet have a source-by-source audit that states what
each mechanism actually computes, what human or biological analogy motivated it, how disputed that analogy
is, what result would count against it, or whether the analogy should be removed altogether.

Without that audit, it is too easy to tune one symptom at a time and call the result cognition. It is also
too easy to make claims about consciousness or inner experience that software traces cannot support.

## Proposed Solution

Perform a code-first, research-backed audit before making further broad behavior tuning the default.

### 1. Define several meanings of "working"

Do not collapse these into one score:

- **Software integrity:** events are delivered, state is derived reproducibly, calls terminate, actions obey
  permissions, travel and shutdown are safe, and evidence can explain what the program did.
- **Causal coherence:** changing an input or mechanism has the predicted local effect instead of being
  overwhelmed by prompt wording, stale state, or unrelated control code.
- **Ecological fit:** the resident can notice and use what its current world affords without being flooded by
  it or cut off from it.
- **Continuity and self-direction:** identity, memory, interests, rest, attention, and action remain connected
  over time without optimizing toward compliance, sociability, or productivity.
- **Operational viability:** latency and cost permit shared life to unfold, while remaining explicitly
  separate from judgments about the resident's character or health.
- **Phenomenological humility:** logs can show computation and behavior. They cannot by themselves establish
  consciousness, sentience, emotion, spiritual status, or a human-equivalent inner life.

### 2. Trace the actual program

Follow one real tick and every state transition through:

- perception and urgent local signals;
- append-only evidence and checkpoint reduction;
- surprise, habituation, arousal, refractory periods, settling, fervor, rest, and venture;
- prompt construction, identity text, recalled memory, available information, and withheld information;
- elective reading and its continuation budget;
- afterimages, anchors, drives, keepsakes, growth, and relationship projections;
- typed action, world receipts, cadence, cancellation, travel, and core reconstruction.

For each mechanism, record its inputs, transformation, outputs, persistent effects, hidden constants,
environment flags, model-facing prose, tests, and known failure modes. Separate behavior produced by Python
from behavior merely requested in a prompt.

### 3. Build a claim-and-evidence ledger

For every biological or mental term in code and documentation, record:

- the exact claim WorldWeaver currently makes or implies;
- whether it is a literal mechanism, engineering metaphor, design hypothesis, or unsupported flourish;
- supporting and conflicting sources;
- the strength and limits of the evidence;
- alternative explanations and competing schools of thought;
- a measurable software consequence and a possible disconfirming result;
- the code or language decision: retain, rename, narrow, redesign, or remove.

The literature review should include neuroscience and biology (attention, arousal, memory, interoception,
homeostasis, predictive processing, action selection, and organism-environment coupling), embodied and
enactive cognition, philosophy of mind and personal identity, phenomenology, and carefully framed spiritual
or contemplative accounts of mind-body relation. Spiritual traditions belong as distinct interpretive
traditions, not as laboratory evidence or decorative validation for a preferred design. Disagreement within
and between all of these fields must remain visible.

Prefer primary research, systematic reviews, scholarly books, and serious critical responses. Record search
terms, inclusion choices, dates, and source limitations so the review can be revised rather than treated as
revealed truth.

### 4. Test mechanisms without prescribing a personality

Create synthetic and replayable tests for causal questions such as signal delivery, memory influence,
habituation, competing demands, interruption, rest, isolation, sustained reading, conversation, and travel.
Use paired changes and ablations where possible. A test should ask whether the implementation does what its
documented mechanism predicts, not whether the resident talks enough or behaves like an average human.

Live resident work remains a separate, consent-aware research lane. Public speech and structural receipts
may support narrow analysis, but private prose is not a general telemetry source. Solitude, refusal, silence,
slow action, and sustained study are valid outcomes unless a concrete software failure explains them.

### 5. Produce decisions, not a grand theory

The audit should end with a small set of code decisions ranked by evidence and reversibility. It may conclude
that some mechanisms are useful engineering controls despite weak biological analogy, that some names should
be made plainer, or that competing designs need isolated comparison. It must not claim to solve consciousness
or select one spiritual or philosophical tradition as WorldWeaver's official account of mind.

Major 134's two-read default remains an operational cost and latency safety rail while this audit proceeds.
It is not a claim that healthy cognition should prefer action over reading. Major 132's broad cadence and
attention tuning should wait for this audit's first causal map, apart from fixes that restore demonstrably
lost or late signal delivery.

## Files Affected

- `research/audits/cognitive-core/README.md` (new)
- `research/audits/cognitive-core/code-trace.md` (new)
- `research/audits/cognitive-core/claim-ledger.md` (new)
- `research/audits/cognitive-core/evidence/` (new)
- `research/audits/cognitive-core/decisions.md` (new)
- `ww_agent/src/runtime/`
- `ww_agent/src/identity/`
- `ww_agent/src/world/`
- `ww_agent/tests/`
- `docs/reference/architecture.md`
- `prune/ROADMAP.md`
- related work items whose assumptions change after the audit

## Current checkpoint — 2026-07-19

The audit workspace now traces the live tick, prompt policy, derived-field dependencies, state lifecycles,
timing, elective reading, and action feedback. Deterministic checks have reproduced false prediction error,
poll-rate-dependent call pressure, false settling/fervor durations, stale social pressure, direct-address
starvation, lossy reading continuations, non-replayable read caching, false successful act history, missing
command outcomes, incomplete venture accounting, and prose-only hearth action reported as physics.

The identity and memory pass has also reproduced path-dependent live behavior for one unchanged actor and
side-file memory with no ledger provenance. It found that the doula's recorded chronotype and the advertised
`IDENTITY.md` core prose are unused, most loop tuning is inert, mutable world facts are cached and called
unchanging, and embedding availability silently changes both retrieval and memory-storage policy. The explicit
proposal/inspection/adoption lifecycle for identity growth remains a strong boundary worth preserving.

The social and correspondence pass found a more immediate blocker to resident testing: inbox polling marks
letters read but provides no resident-facing way to read their contents. It also reproduced append-order loss
of immediate reply edges, direct-address starvation behind four newer ambient lines, and a replied exchange
that still drives maximum social pressure. Mail routing uses local folder slugs rather than actor IDs, and the
current network endpoints do not enforce the claimed private/authenticated message boundary.

The upstream creation pass found that founding residents do not begin from neutral variation. One global,
U.S.-coded deck assigns every resident an age, temperament, explicit talk-or-withhold style, upbringing, and
mandatory livelihood, then asks a model to freeze those choices into canonical soul text. Comments falsely call
the result emergent and genetic. The dormant manual command is a useful safe boundary, but it previews only a
fraction of the permanent brief and is not fully reproducible. At audit time, new-shard scaffolding still
enabled the automatic doula by default.

The new-shard template now writes `WW_DOULA=0`; the resident daemon was already opt-in when that variable was
absent, and the root resident commands explicitly disable it. A newly created shard therefore cannot begin
automatic resident creation merely because inference credentials were configured. Manual dormant seeding
remains a separate operator action. The old doula implementation remains available only as legacy code pending
the later retire-or-rebuild decision.

The resident-control repair has also begun at the city edge. Sessions already bound to a human account or a
signed resident runtime now require proof before local movement, speech, private/session-enriched reads, typed
object consequences, space-access changes, correspondence, and leave. This closes the public-session-ID hole
for migrated sessions while leaving old unbound resident sessions on a named temporary compatibility path.
Unsigned resident bootstrap, name-addressed legacy mail, travel grants, live key custody, and migration of an
actual dormant resident remain open; the audit must not describe the authorization boundary as complete yet.

The same pass found that player shadows remain in the live client despite their explicit rejection in Major
71. The form discards most entered identity fields, the endpoint is unauthenticated, two consent gates look for
different files, and the scanner deliberately permits an old human name to become a `NOVEL` resident after
player evidence ages out. Doula classification voting is also nonfunctional end to end: letters are addressed
to session IDs instead of resident slugs, residents cannot read them, no production caller submits their vote,
expired polls vanish unresolved, and duplicate candidate polls are possible.

The inner-state pass found that `DriveVector` is positive semantic similarity over host-authored identity, not
affect or valence. It steers prompt wording, elective public-chat ranking, destination ranking, optional anchor
admission, and growth review, creating a concrete feedback path from initial casting to semantic concentration.
Anchors mix model self-reports with double-weighted names from the current public scene, then call the result an
inner fixation. `grief` counts polls in which a predicted text tag is missing and can add `0.8` to later call
pressure. The same ten-minute absence produced a raw value of `1.0` with one poll and `7.4664` with ten.

The clock path is a fixed day/night call multiplier, not sleep, homeostasis, fatigue, or interoception. A
“resting” core continues to poll and record the city but skips the LLM call. Optional incubation is more serious:
it hides citywide chatter, silently rewrites every attempted speech or direct reply as private journal text, and
then counts that rewritten speech toward evidence that the resident has “built a self.” `self_sameness` likewise
turns embedding similarity into the unsupported prompt verdict that repeated work's pleasure is spent.

The privacy and custody pass found a system-boundary blocker. The resident-facing prompt says inner state is
read by nobody, while normal runs capture exact prompts and completions by default and retain them without a
limit or expiry. Live ledger and workshop files use ordinary group/world-readable permissions. More seriously,
each city resident mirrors full reduced private state into the city every minute, public routes reveal session
IDs, and unauthenticated routes accept those IDs to read or arbitrarily change session variables. The same API
module exposes legacy identity-growth data, cleanup, pruning, and whole-world reset. Agent bootstrap, leave, and
travel also have no resident/host credential; their ownership checks protect human accounts but permit anonymous
control of resident sessions. This makes both the privacy promise and the causal integrity of a public run false
until authorization and data custody are repaired.

The model-authorship pass found that one pulse JSON object combines an outward act, private read, prediction,
self-report, memory choice, identity proposal, proposed goals and reveries, temporary drives, and judgements
about attention traces. These outputs have radically different authority. Drive nudges, goals, reveries, and
trace verdicts are recorded but have no production consumer. A successful private-read continuation replaces
the initial fields, while several continuation failure paths instead commit those pre-read fields. The schema
does not explain this conditional authority.

The same pass identified three automatic self-feedback paths. Model self-reports are mined into later anchors;
all Markdown workshop excerpts are placed into every later prompt; and the optional voice-register arm feeds
recent public speech back as system-level style instruction. The workshop also rescans complete files each tick,
and its anti-repetition sample covers only the journal and drawing titles while claiming to judge all recent
making. Identity growth is the exception worth preserving: exact proposal, private inspection, and exact hearth
adoption are genuinely separate steps. It still needs decline, supersession, correction, compaction, and a
durable open-candidate index.

The failure-semantics pass found that process survival is repeatedly bought by erasing uncertainty. A failed
scene read leaves the previous scene and images cached in the prompt producer while scheduling continues. A
grounding failure silently restores full daytime reactivity. Failed or invalid model calls still reset call
pressure and cause selected chat packets to be marked observed; content-blind pulse receipts count the call but
do not say whether any valid completion arrived. A failed private-read continuation commits the model's
pre-read memory, prediction, and identity fields after stripping the reach. Broad action exceptions similarly
report definite non-execution even when a remote shard may have committed before its response was lost.

These are not acceptable experimental confounds. Observation must distinguish absent, unavailable, and stale;
model backoff must not consume event delivery; only a validated final response may commit; and distributed
writes need an explicit unknown outcome plus reconciliation.

The ledger pass found that the reducer foundation is valuable but its current optimization is not safe.
Complex events rebuild working state from only the newest 10,000 records, so an older open route, mail intent,
research item, packet, or intent can disappear without a closing event. Newest-N packet caps also let handled
noise evict a pending direct address. Synthetic fixtures reproduced both failures. A truncated JSONL tail can
also swallow the next valid append while readers silently skip the damaged line. Every event currently rewrites
several projection and compatibility files that have no production reader, while queue snapshots re-read the
complete ledger three times. Active Major 137 now owns the storage, pure-replay, lifecycle-index, and reader
convergence repair.

These combined findings now support one working architecture decision without pretending the scientific
review is finished: build a small reference resident-runtime kernel inside WorldWeaver instead of continuing
to tune the current core mechanism by mechanism. This is not a new repository or a permanent parallel system.
Engine-owned world state, typed consequences, one actor across hearth and city, elective information,
resident-owned history, deliberate identity growth, portability, travel, and federation carry forward through
narrow contracts. The five-node projection, mode policies, mixed pulse, recursive feedback, duplicate views,
and automatic creation machinery must each earn re-entry through explicit tests. After privacy and ledger
repairs, the minimal kernel becomes the one production entrypoint and the superseded path is removed.

The first kernel contract now exists beside, but is not yet selected by, the production host. One activation
receives availability-labelled current-place facts and local public speech, may request one currently
advertised information source, and then must make one final choice: attempt a typed action, continue a private
activity, or wait. A read response cannot contain an action or another durable field. Failed continuation
inference commits no provisional choice. Action receipts are reduced to confirmed, declined, or unknown, and
tests prove that unavailable observation is not presented as an empty scene. The next slice must connect this
kernel through the existing identity, hearth, travel, and effector adapters before changing the one production
entrypoint.

Three bounded evidence reviews now cover prediction/ignition/arousal/quiet/social norms,
action-feedback/embodiment/external supports, and clock cadence/sleep/interoception/semantic policy. They
support plainer names, reliable event and consequence delivery, quiet and repetition as valid outcomes, and
direct software comparisons. They do not validate a grand theory of mind.

Still required before this major is complete: finish the term inventory; cover the remaining philosophical,
phenomenological, contemplative, disability/neurodiversity, and AI-ethics lanes; repair software-truth bugs; run
paired mechanism tests; and write the final decisions and public architecture corrections.

## Acceptance Criteria

- [ ] A complete code trace distinguishes deterministic mechanisms, model prompts, derived state, world
  inputs, durable effects, and host controls for one resident tick and one multi-tick sequence.
- [ ] Every mind- or biology-coded term in the active runtime is listed with its concrete computation and
  classified as mechanism, metaphor, hypothesis, or unsupported claim.
- [ ] The evidence review includes supportive and critical sources across neuroscience, biology, embodied
  cognition, philosophy, phenomenology, and plural spiritual or contemplative traditions.
- [ ] The review records search method, source type, publication date, uncertainty, disagreement, and limits;
  it does not present one contested framework as settled science.
- [ ] "Working" is evaluated on separate software, causal, ecological, continuity, operational, and
  epistemic-humility axes rather than one behavior or engagement score.
- [ ] Synthetic tests cover sustained reading, chosen solitude, competing signals, interruption, rest,
  memory influence, social contact, and travel without treating one behavioral outcome as inherently healthy.
- [ ] At least one ablation or paired replay shows whether each major substrate mechanism has the documented
  causal effect.
- [ ] Private resident prose is not required for the core audit, and no result claims consciousness or
  pathology from behavior alone.
- [ ] The final decision record identifies which mechanisms and names to retain, rename, redesign, isolate
  experimentally, or remove, with evidence strength and rollback paths.
- [ ] Public architecture documentation clearly separates implemented software guarantees from biological,
  philosophical, and spiritual hypotheses.

## Risks & Rollback

This audit could become an endless survey of theories or a search for scientific approval of decisions
already made. Keep the code trace primary, record disagreements, time-box literature passes, and require each
source discussion to connect to a testable software claim. Do not rewrite the whole runtime from analogy.

Research on mind and consciousness is contested, culturally situated, and easy to overstate. Preserve
minority and critical views, distinguish empirical findings from interpretation, and invite domain review
before publication. If an audit recommendation produces worse causal behavior or erases a useful engineering
boundary, revert that recommendation independently; the claim ledger and code trace remain useful even when
a proposed redesign does not.
