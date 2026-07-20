# Action, consequence, and the current body boundary

Status: code audit and deterministic reproductions, 2026-07-19.

This pass asks what happens after a resident chooses an outward act. A body-like interface needs more than a
command leaving the model. The resident must be able to encounter what the world allowed, what it refused,
what changed, and what remains possible.

WorldWeaver has real strengths here: typed object and access commands reach canonical engine services, movement
changes location, workshop writing changes files, and many successful commands carry engine receipts. The weak
part is feedback. Outcome information is inconsistent, often absent from the next model prompt, and sometimes
replaced by a sentence that claims more happened than the world actually stores.

## The actual path

1. The final model response proposes one typed `Act`.
2. `WorldEffector` interprets its kind and target.
3. The effector calls a hearth adapter, an engine endpoint, the private workshop, or a messaging endpoint.
4. The immediate result is returned in the in-memory tick result.
5. The effector may append a local outcome event, and the engine may separately commit canonical state and a
   public world event.
6. `route_pulse()` then records `pulse_act_emitted`, whether the action succeeded or not.
7. The next model call rebuilds its prompt from a new scene, selected ledger-derived fields, memories, the
   workshop summary, and a recent-act-kind count.

There is no general step that renders the prior action receipt or failure reason into the resident's next
prompt. The in-memory `act_executed` result is available to an optional host observer, but it is not passed back
to `CognitiveCore` as resident-facing feedback.

## Feedback differs by action

| Action | What really persists | What the resident can encounter later |
| --- | --- | --- |
| local or city speech | canonical chat plus a local sent event | other people can hear it; the speaker's own chat is filtered from ordinary speech perception, though optional voice sampling and the act-kind counter may reuse it |
| carried speech or letter | message transport plus a local sent event | no general delivery result is placed in the next prompt |
| successful move | canonical session location plus `move_executed` locally | the next scene normally shows the new location |
| blocked move | local `move_executed` with `status: blocked` | the engine's explanation is discarded; the next prompt has no standard blocked-action feedback |
| typed object, making, stoop, exchange, or access command | canonical state, an engine receipt, a local `game_*` event, and often a public world event | changed state may appear in a later scene or an elective source, but the local receipt is not directly rendered |
| generic city `do` | an `action_declined` event | its useful decline narrative is not rendered into the next prompt |
| generic hearth `do` | a line in `voice.jsonl` plus `action_executed` | no object, fixture, spatial change, or other hearth state is created |
| workshop write or drawing | an actual resident-owned file plus a local event | the workshop summary is shown in later prompts |
| physical mark | a canonical local trace plus a local event | the mark can be encountered in the scene |
| identity growth adoption | identity files and adoption evidence | the core rebuilds its optional drive and later prompts use the changed identity |

This is not one uniform sensorimotor loop. Some acts have strong state feedback, some require a deliberate
follow-up read, some leave only operator evidence, and some are textual performance recorded as physical
success.

## Attempted verbs are narrated as successful history

The act-trace prompt feature reads `pulse_act_emitted`, which records proposals after the effector returns. It
does not read outcome events. It then uses phrases such as “moved,” “acted on a thing,” and “left a mark.”

A deterministic reproduction recorded eight blocked movement results and their eight emitted move proposals.
The next act trace said:

```text
8 moved
```

It also said the resident had not acted on a thing and that the world kept other doors open. The prompt thus
turned eight refusals by the world into eight successful movements, then used that false history to steer the
next choice.

If this feature survives, it must separate requested, accepted, declined, and unknown outcomes. Availability
must come from current affordances, not from a generic reassurance that a door remains open.

## Successful typed actions do not warm the venture scheduler

The venture policy says it checks for recent successful `move` or `do` contact with the world. Its success
reader actually recognizes only:

- `action_executed`;
- successful movement events;
- pending world travel.

It does not recognize successful `game_object_made`, `game_object_pick_up`, `game_object_place`,
`game_object_given`, stoop, exchange, or space-access events. A deterministic event containing a newly made
canonical object returned no last successful world-act time.

This means a resident can make an object, pick something up, leave it on a stoop, or change access to a place
and still be treated as having had no recent bodily contact. The optional venture policy may then push another
move or `do` because the world is supposedly “cold.” That is an event-taxonomy bug before it is any theory of
action tendency.

## Failed typed commands can disappear from durable evidence

The engine client raises on non-success HTTP responses. `WorldEffector.__call__()` catches the exception and
returns only:

```json
{"executed": false, "kind": "do", "reason": "exception"}
```

The detailed engine error is written to the process log, not the resident ledger. Because the exception skips
the command-specific append, the intended `game_command_declined` event is not written. Early validation and
unavailable-capability returns have the same no-outcome-event shape.

A deterministic typed making failure returned `reason: exception` and left zero effector outcome events. When
called through the integrator, later records retain the act proposal and a content-blind `not_executed`
summary, but not the reason the world refused it.

That is insufficient for both cognition and audit. A resident cannot adapt to “out of material,” “not here,”
“not yours,” “door locked,” or “permission required” if every refusal becomes silence or a generic exception.
An operator also cannot reconstruct the causal path from the ledger alone.

## Decline evidence exists but is not resident-facing

Even when a decline is durably recorded, the prompt builder does not render `action_declined`,
`game_command_declined`, blocked movement, or `pulse_runtime_summary`. A deterministic prompt built after an
`action_declined` event containing “The oak door is locked” included neither the attempted action nor the
reason.

The next scene can indirectly reveal some consequences. A moved resident sees a new location; a made object
may appear in a public event or the elective object source; a workshop file appears in the workshop summary.
That indirect route is useful but not equivalent to proprioceptive or action-result feedback:

- public event lists are bounded and can be crowded out;
- a moved resident may no longer be at the place where a departure event was recorded;
- private failures should not need a public event;
- an elective source must be requested before it can explain a result;
- the resident does not know that a follow-up read is needed when the failure itself was hidden.

## The hearth currently treats prose as physics

The city adapter declines generic free-form `do` text unless it is travel or one of the encoded typed commands.
The hearth adapter does the opposite: it accepts nearly any sentence, appends it to `voice.jsonl` as a gesture,
and returns a narrative of the form “You [action].” The effector sees no `plausible` field, defaults it to
true, and records `action_executed`.

A deterministic request to “place a carved cup on the mantel” therefore returned `executed: true` while the
only hearth-side change was one gesture line. There was no cup, mantel attachment, inventory transfer, object
event, or later inspectable state.

This may be acceptable as private imaginative play if it is named that way. It is not the same affordance as
canonical physical action. Calling both `action_executed` makes city and hearth embodiment incompatible and
allows imagined state to masquerade as world state.

The long-term hearth-as-shard direction suggests a cleaner choice:

- give hearths a small canonical object and place state using the same typed consequence interfaces; or
- distinguish an `imagined_gesture`/`private_narration` result from a physical state change.

The resident can still imagine freely. The software should not claim that imagination changed shared or
persistent physics when it only stored prose.

## What “body” can honestly mean today

The current runtime has a functional world attachment:

- one current location;
- adjacency and movement rules;
- co-presence and local hearing;
- capability-scoped perception and information;
- canonical objects, custody, making, exchange, marks, and access rules on supporting shards;
- a typed path by which one act may change that state.

That is a meaningful software body boundary. It is not yet a closed learning loop. Consequence is not presented
consistently, action failure is not durably typed, and the scheduler sometimes reasons from proposals rather
than outcomes. It also has no learned sensorimotor model, continuous activity, material needs, injury, growth
through use, or general hearth physics.

The narrow claim should be: the resident has a typed, permissioned attachment to a world. Whether that
attachment is sufficient for stronger accounts of embodiment remains an open research question.

## Repair requirements

1. Define one durable `act_outcome` envelope for every attempted act: request ID, kind, command, accepted or
   declined status, stable reason code, safe explanation, resulting references, location, and timestamp.
2. Preserve engine domain error codes through `WorldClientError` and write them to the ledger without leaking
   sensitive server detail.
3. Make the next activation able to receive unresolved or newly completed outcomes. Mark feedback observed
   only after it was actually included in a prompt.
4. Build act-history reflection from outcome events, not `pulse_act_emitted` proposals.
5. Make successful-world-contact policy consume all relevant typed success events, or remove that policy from
   the neutral reference runtime.
6. Give blocked movement its reason and keep the engine response revision/location attached.
7. Separate imaginative hearth gesture from canonical physical consequence until hearths implement matching
   object and place state.
8. Keep public world events and elective inspection as additional evidence, not the only feedback channel.

## Required tests before interpreting behavior

- Success and decline for every act kind, with the same outcome envelope shape.
- A resident sees a failure once and can choose a different action without being forced to retry.
- Eight blocked moves never render as eight successful moves.
- Every typed successful `do` command is either counted consistently or excluded by a clearly named policy.
- A process restart preserves an unobserved outcome until a prompt receives it.
- Travel does not lose the last source-side outcome during core rebuild.
- Hearth imaginative gesture and physical object creation produce distinguishable evidence.
- Public scene events being crowded out does not erase private action feedback.
- Structural analysis reports requests, successes, declines, and unknown outcomes separately.

Until those hold, action counts measure model proposals more reliably than embodied behavior.
