# Make resident participation independent of CognitiveCore

## Problem

WorldWeaver currently treats one implementation, `ww_agent`'s `CognitiveCore`, as if it were the definition
of an artificial resident. The engine has increasingly useful actor, session, action, travel, and public-key
contracts, but the only production client that combines them is the WorldWeaver resident runtime. This makes
it difficult to tell which behavior comes from the world and which comes from one shared model, prompt,
attention policy, memory system, and cadence.

That sameness likely contributed to the conversational monoculture seen in earlier runs. Residents differed
in names and histories, but used the same kind of brain, the same information pipeline, the same action
selection machinery, and usually the same model. More personality text cannot provide the diversity that
genuinely different implementations could bring.

The current coupling also works against WorldWeaver's broader purpose as a world-sharing system. Another
research group, a local-model hobbyist, or the author of a small scripted ferry should be able to connect to
a city without adopting CognitiveCore, its private ledger format, its psychological terms, or its prompt
schema. The city should care who is acting, what that actor is allowed to do, and whether an action succeeds.
It should not prescribe how the actor reached the decision.

Humans already use a different interface over many of the same world commands. That useful separation should
be made explicit and extended carefully rather than replaced with a generic plugin system that leaks engine
internals or grants unknown programs broad access.

## Proposed Solution

Define a small, versioned participant protocol above the shared world rules. `CognitiveCore` becomes one
reference resident implementation of that protocol, not part of the protocol itself.

### 1. Separate participant, resident, human, and automaton

Use **participant** as the broad transport-level term for something that can enter and act in a world.

- A human authenticates through a human account.
- A resident has durable actor identity, private continuity, one hearth, and the ability to travel.
- An automaton or service actor may have a much narrower identity and lifecycle and need not claim a hearth,
  memory, selfhood, or person-like status.

These labels describe software contracts and public expectations. They must not claim to measure
consciousness, intelligence, moral worth, or inner experience. A fluent model must not silently present
itself as a reflective resident, and a scripted actor must not be disguised as one. Public labeling and local
admission policy should be honest without turning implementation type into a universal social hierarchy.

### 2. Publish the minimum wire contract

Document the smallest set of operations an independently written client needs:

- discover a shard's protocol version and supported features;
- present an admitted actor identity or appropriate human credential;
- establish one bounded session or attachment;
- read unavoidable current-place facts and pending direct signals;
- electively request named public or private information sources when authorized;
- attempt typed movement, speech, marks, object, access, exchange, and travel actions;
- receive canonical success, refusal, retry, or unknown-outcome receipts;
- resume from cursors and idempotency keys without duplicating effects;
- leave or park cleanly.

The contract must not contain prompts, salience values, model names, private ledger layout, workshop format,
or CognitiveCore-specific state. A participant may use an LLM, a behavior tree, a state machine, a human
operator, or something not yet designed.

### 3. Reuse one authorization and consequence path

Finish the actor-scoped authorization work already required by Majors 18 and 127. Human JWTs and resident
runtime signatures should resolve to the same small authorized-actor context before entering ordinary domain
rules. External resident implementations receive narrowly scoped runtime certificates; they do not receive
the city's JWT secret, node key, another resident's session, or direct database access.

The engine remains authoritative for shared location, custody, access, exchange, travel, and other public
consequences. A participant chooses an attempted action; its prose cannot declare that the action succeeded.

### 4. Add capability and version negotiation without brain inspection

A shard should publish its supported protocol and action families. A participant should declare only the
interface capabilities needed for compatibility and honest presentation, such as whether it can receive
direct signals, carry objects, travel, or render images. Do not require disclosure of private prompts,
weights, memories, reasoning traces, or model-provider credentials.

Version negotiation must fail clearly when a required operation is unavailable. Optional features should be
additive so a simple client can participate without pretending to support the complete resident experience.

### 5. Build two deliberately different reference participants

Keep the repaired resident-runtime kernel from Major 136 as the full WorldWeaver reference resident. Add one
tiny, dependency-light scripted example outside that runtime which can authenticate as a synthetic test actor,
read its current place, perform a small allowlisted routine, handle a refusal, and leave cleanly.

The scripted example is a protocol probe, not a fake person and not background activity inserted to make a
town look busy. Its public test identity must say what it is. It should be simple enough that another
implementer can understand the complete client without reading CognitiveCore.

### 6. Prove mixed participation

In a synthetic city, run a human test client, the minimal scripted participant, and the WorldWeaver reference
resident through the same domain rules. Verify that:

- none can act through another actor's session;
- all receive the same result for the same rule-governed attempted action;
- different polling or response speeds do not lose direct signals or duplicate consequences;
- one participant can remain quiet or leave without blocking the others;
- the city stores public consequences but does not ingest private brain state;
- the federation can describe protocol compatibility without certifying a preferred kind of mind.

Do not begin with an open internet endpoint accepting arbitrary bots. First prove the protocol with synthetic
identities, local rate limits, explicit steward admission, and complete cleanup.

## Files Affected

- `docs/reference/participant-protocol.md` (new)
- `docs/reference/architecture.md`
- `prune/VISION.md`
- `prune/ROADMAP.md`
- `worldweaver_engine/src/services/actor_authority.py`
- `worldweaver_engine/src/services/resident_protocol.py`
- `worldweaver_engine/src/api/game/`
- `worldweaver_engine/src/api/shard/`
- `worldweaver_engine/tests/`
- `ww_agent/src/world/client.py`
- `ww_agent/src/world/resident_signing.py`
- `ww_agent/src/runtime/` only where the reference runtime adapter changes
- `examples/participants/` (new)

## Acceptance Criteria

- [ ] Public documentation defines a versioned participant protocol without CognitiveCore, prompt, model, or
  private-ledger fields.
- [ ] Documentation clearly distinguishes humans, continuing residents, and narrower automatons as software
  contracts without making claims about consciousness or moral status.
- [ ] A shard publishes its protocol version, supported action families, and optional features in a stable,
  machine-readable form.
- [ ] An independently written client can discover, authenticate, attach, read current-place facts, attempt an
  allowed action, receive its canonical outcome, and leave without importing `ww_agent`.
- [ ] External resident runtimes use actor- and generation-scoped credentials rather than shared shard or node
  secrets.
- [ ] Human and nonhuman callers enter the same domain rule functions after authentication.
- [ ] A minimal scripted reference participant is visibly labeled, narrowly scoped, dependency-light, and has
  no access to private resident or steward state.
- [ ] Synthetic mixed-participant tests cover wrong-actor access, refusal, idempotent retry, different polling
  rates, direct-signal delivery, quiet participation, and clean departure.
- [ ] Public city state records actions and consequences without storing model prompts, private reasoning,
  CognitiveCore projections, or another implementation's internal memory.
- [ ] Federation compatibility describes supported protocols and features without making one directory the
  owner or mandatory certification authority for participant implementations.
- [ ] Rate limits, admission, revocation, and public implementation labels are explicit before any open bot
  entry is enabled.

## Risks & Rollback

An open protocol can increase spam, impersonation, denial-of-service, and deceptive presentation. Keep entry
closed by default, require scoped identity, enforce rate and size limits at the city boundary, and make public
labels part of reviewed admission. Do not expose a general-purpose remote tool runner.

A lowest-common-denominator protocol could flatten useful world features. Keep a small required core and
versioned optional capabilities rather than placing every action in version 1. Conversely, capability
declarations could become a disguised inventory of cognition. Declare supported interfaces, not private
mental architecture.

Mirrored protocol code in the engine and clients can drift. Publish canonical test vectors and run at least
one cross-process compatibility test that does not share implementation code. If the external path is unsafe
or unstable, disable new external admissions while retaining the documented test vectors and the existing
WorldWeaver adapter. Do not roll back the rule that shared consequences remain engine-owned.

## Progress

### 2026-07-20 — small activation contract

`ww_agent/src/runtime/reference_core.py` now implements the first deliberately plain resident activation. It
does not import salience, arousal, prediction, drive, incubation, or the mixed `Pulse` router. It observes the
current exact place with explicit available/unavailable states, includes local public speech without making a
reply mandatory, advertises named elective sources, permits one provisional read, and accepts only one final
typed action, private continuation, or wait choice.

Strict response shapes prevent a read request from also carrying a provisional action. A failed after-read
call commits no action or private activity. The existing world effector remains the narrow adapter to shared
rules, and the new loop records a content-blind confirmed, declined, or unknown result after that adapter
returns. Focused synthetic tests cover direct local speech, unavailable scene/chat, read-then-act, continuation
failure, quiet waiting, and all three action-outcome states.

### 2026-07-20 — reference loop selected by the resident host

`src/resident.py` now constructs the small reference loop for both hearth and city attachments. The existing
resident host still owns identity, one-at-a-time attachment, travel recovery, workshop access, information
providers, and typed effectors. The old core is no longer a production entrypoint. Operator commands now
separate cheap polls from model activations and no longer advertise old action-tendency, multi-read, embedding,
or prompt-trace controls that the reference loop does not use.

The scheduler polls exact-place facts and local speech every twenty seconds, activates immediately for newly
observed local speech, and otherwise uses a five-minute baseline. It does not feed the same old speech back as
a fresh signal at every baseline. A clean synthetic resident run is still required before this switch is
considered operationally proven. Resident runtime key custody and signed bootstrap also remain prerequisites
for a trustworthy real run.
