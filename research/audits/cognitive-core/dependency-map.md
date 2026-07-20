# CognitiveCore dependency map

Status: code-truth pass completed 2026-07-19. This map answers one narrow question: after a value is
computed or returned by the model, what reads it next?

The categories are deliberately plain:

- **controls behavior** means the value can change model-call timing, prompt contents, information access,
  or an outward action;
- **operational only** means it supports status, debugging, or a report but does not change the resident's
  next decision;
- **stored only** means current production code writes it but has no production reader;
- **copied outward** means it leaves the resident's local hearth folder and is placed on a shard.

## Reduced projections

| Projection or field | Actual downstream readers | Current effect | Finding |
| --- | --- | --- | --- |
| `runtime_projection` | subjective and cognitive reducers; runtime mirror | Indirectly controls the five node values through recent movement, mail, research, and event records | Live, though its whole payload is also copied outward unnecessarily |
| `subjective_projection.state_pressure` | cognitive reducer; daily digest; runtime mirror | Controls vigilance, mobility, and rest inputs | Live |
| `subjective_projection.dialogue_state` | cognitive reducer; daily digest; runtime mirror | Direct questions and requests produce fixed urgency values that raise `social_pull` | Live, with normative policy mixed into descriptive state |
| `subjective_projection.mail_state` | cognitive reducer; runtime mirror | Inbox count raises social and correspondence values | Live |
| `subjective_projection.active_social_threads` | cognitive reducer; runtime mirror | Thread count raises `social_pull` | Live |
| `subjective_projection.current_concerns` | cognitive reducer; runtime mirror | Selected concern kinds become evidence and sometimes fixed activation floors | Live, but Python decides which concerns count |
| `subjective_projection.world_salience` | runtime mirror | No resident-runtime reader | Operational/stored only |
| `memory_projection` | daily digest; runtime mirror | Does not feed the resident's prompt or scheduler; durable keepsakes use a separate reader | Operational only |
| `subjective_facts` | cognitive projection's evidence count; runtime mirror | The facts themselves do not feed the prompt, scheduler, or actions | Stored/counted only |
| `relationship_projection` | nested in subjective projection and subjective facts; runtime mirror | No resident-runtime reader | Stored only |
| cognitive node `activation` | salience stimulus; pulse prompt | Changes surprise, arousal, call timing, and the prose shown to the model | Live and load-bearing |
| cognitive node `mode` | pulse prompt | Changes labels shown to the model, such as `withdrawn`, `wary`, and `tired` | Prompt steering only |
| node `stability`, `persistence_class`, `sticky_until`, `neighbor_bias`, `refractory_until`, `evidence_refs` | checkpoint/mirror/tests | No later cognitive reader applies these values | Decorative or diagnostic only despite graph-like contract language |
| `active_nodes` and `evidence_summary` | checkpoint/mirror/tests | No resident-runtime effect | Operational only |
| `_resident_rest` | city roster/status and rest metrics | Changes how the city reports the resident, not cognition itself | Operational and externally visible |

## Model pulse fields

| Pulse field | What happens after generation | Current classification |
| --- | --- | --- |
| `act` | One validated act may reach the world effector | Direct outward control |
| `reach` | A named private source may be read, followed by a bounded continuation call | Direct information control |
| `expectations` | Stored as decaying afterimages and compared with later stimulus | Direct scheduler control |
| `keep` | Written to durable memory, returned in later prompts and elective recall, and counted by incubation | Direct continuity and prompt control |
| `felt_sense` | Stored; offered by elective recall; mined for noun phrases used as future anchors; those anchors return in prompts and may enter arousal when anchor gating is enabled | Indirect behavioral control, contrary to the prompt's claim that it is “never acted on” |
| `self_delta.soul_edit` | Staged behind a code gate and may later be explicitly adopted | Governed identity-change candidate |
| `self_delta.new_reverie` | Staged as an event | Stored only; no production adopter or reader found |
| `self_delta.goal_update` | Staged as an event | Stored only; no production adopter or reader found |
| `drive_nudges` | Stored as decaying `drive_nudge_cast` events | Stored only; `active_drive_nudges()` has no production caller |
| `trace_verdicts` | Stored as `trace_verdict_recorded` events | Stored only; no production reader found |

## Two verified causal mismatches

### `felt_sense` is not readout-only

The output contract says `felt_sense` “is never acted on.” It is true that the text is not sent straight to
the world effector. It is not true that the field is causally inert:

1. `route_pulse()` writes it as `felt_sense_logged`.
2. `CognitiveCore.tick_once()` reads the latest ten lines.
3. `extract_anchors()` pulls recurring noun phrases out of them.
4. The resulting anchors are placed in later reactive prompts.
5. With per-resident anchor gating enabled, soul-resonant anchors also enter the stimulus field and can
   change surprise and arousal.
6. The `recall` information source can return prior felt lines to the model.

The honest contract is therefore: this is private model-authored self-description; it never directly causes
an outward act, but it can shape later prompts and, under an optional gate, call timing.

### Predictions are advertised for sensing lanes that do not exist

The contract permits expectations with scope `self`, `here`, or a person's name. Normal stimulus contains
only the five `self` features. Optional anchor gating adds `anchors`; it does not add place or person fields.
`measure_surprise()` compares the union of predicted and observed scopes, treating a missing observed value
as zero. A model prediction such as `here::warmth=0.8` therefore becomes a `0.8` surprise even though no
place-warmth sensor made an observation.

A direct function check confirms the behavior:

```text
stimulus:   self::social_pull=0.0
prediction: here::warmth=0.8
result:     magnitude=0.8, here::warmth observed as 0.0
```

This is manufactured evidence of absence. Until place/person stimulus fields exist, the contract should
accept only `self` and the separately governed `anchors` scope, or surprise must ignore scopes for which no
observation was possible.

### Direct questions do not close when answered or when their stated timer passes

The subjective reducer gives direct questions a five-minute “expiry window,” but compares each question's
timestamp with the newest direct-message timestamp, not with the current time. The newest direct question is
therefore always fresh by definition. The reducer also processes packets regardless of their `pending` or
`observed` status and does not consult the relationship projection that records an actual reply edge.

Consequences:

- a perceived and answered question can remain in `open_questions`;
- `direct_urgency` can remain `1.0`;
- `social_pull` can remain fully active;
- `owes_reply_to` can remain present after a recorded reply;
- mail and social-thread counts similarly describe retained packet history as current pressure.

The state eventually changes only when later packets push the old packet outside the bounded projection or a
fresh ledger horizon no longer contains it. That is storage churn, not semantic resolution.

## Outward mirror and privacy boundary

Every minute, a city resident currently copies all five reduced projections, subjective facts, ledger event
count, and rest state into engine `SessionVars`. Most of this data is not needed by the city. The federation
pulse uses location and status. The public roster uses location, display information, and rest state. The
daily digest uses a few aggregate fields.

More seriously, `GET /api/state/{session_id}/vars` returns raw session variables and has no authentication
dependency. The game router has no enclosing authentication dependency either. Public roster responses expose
session IDs, so the identifier is not a meaningful secret. As implemented, the city briefing's statement that
inner state “is not read by anyone” is false: reduced inner-state data is copied to the shard and can be fetched
through its HTTP API.

This is a privacy and data-minimization problem independent of whether any steward has used the endpoint. The
narrow repair should be designed before further resident runs:

1. stop mirroring private projections by default;
2. send only an explicit public operational status contract;
3. authenticate and authorize any remaining raw state endpoint;
4. separate resident-private diagnostics from shard-public status;
5. correct the situational briefing so it never promises stronger privacy than the software enforces.

## Dead-state consequence

The pulse contract asks every model call to produce several fields that have no live consumer. This costs
attention and tokens, gives the interface a false appearance of depth, and leaves misleading evidence in the
ledger. In particular, the default schema example names a `curiosity` drive even though current code has no
production reader for drive-nudge events. The source comment says this becomes a self-reinforcing pull; that
comment describes an older or intended architecture, not the present one.

The audit should distinguish “remove the unused field” from “finish the missing mechanism.” Neither choice
should be made merely because the field has a cognitive-sounding name.
