# CognitiveCore repair and ablation order

Status: proposed from verified code findings. This is not yet a claim that any particular cognitive theory is
correct.

## First: repair software truth

These are not behavioral experiments. They are contradictions or lifecycle bugs that prevent later evidence
from being interpretable.

1. **Restore the privacy boundary.** Replace the full runtime mirror with a minimal public operational payload
   and protect any diagnostic endpoint with authentication plus actor/steward authorization.
2. **Stop false prediction error.** Accept expectations only for sensed scopes, or represent an unobserved
   scope as unknown rather than zero.
3. **Make time semantics true.** Remove poll-rate dependence from repeated evidence, give replays a virtual
   clock, and stop calling time-since-last-pulse time-in-band.
4. **Resolve social state from lifecycle evidence.** Pending prompt delivery, observed history, unanswered
   address, and replied exchange must be separate. Use wall time and canonical reply edges.
5. **Give direct address a lossless attention path.** A newly addressed event must reach attention even when
   an aggregate social node is saturated, without forcing a reply or an outward act.
6. **Write empty current snapshots.** A calm scene must clear old ambient pressure.
7. **Make the pulse contract true.** Correct the description of `felt_sense`; remove dead fields from the live
   schema or give them an explicit, justified consumer.
8. **Choose one memory authority.** Treat kept-memory materialization as a rebuildable index or derive it from
   the append-only ledger.
9. **Use the current checkpoint/projections for live reads.** Preserve complete cold history for audit without
   repeatedly rebuilding it on every tick.
10. **Correct the archived/current docs.** Do not claim valence, reverie-weighted drive, semantic constitution
   gating, or node-neighbor plasticity until the live path proves them.
11. **Make the information episode contract true.** Stop calling a reach-enabled pulse one LLM call, define
   whether only the final continuation commits, return cached results to the requesting model, and use an
   injected clock for replayable cache behavior.

## Second: establish a neutral reference runtime

The reference arm should retain only:

- exact-place observation with explicit pending/observed lifecycle;
- typed elective information sources;
- one optional outward act;
- selected durable memory;
- immutable canonical identity plus explicit growth provenance;
- permissions and world consequences;
- content-blind operational receipts.

Host resource limits should be explicit in this reference arm, but they should report calls, tokens, time,
and cost as host constraints rather than presenting a fixed read count as a theory of attention.

Add one small resident-owned inquiry lifecycle after the truth repairs: start, checkpoint, pause, resume, and
close. It should retain source references and structural progress, not hidden chain-of-thought. A new embodied
event may interrupt the task without forcing a reply or destroying the resident's place in it.

It should remove mode metaphors, stock life examples, anti-repetition judgements, unused pulse fields, and
unsupported health language. Quiet, reading, repeated practice, refusal, speech, making, and movement should
all remain valid results.

This is a reference condition, not automatically the final design.

## Third: paired mechanism tests

Each row changes one causal surface while replaying the same recorded public/structural inputs.

| Question | Control | Treatment | Content-blind or structural measures |
| --- | --- | --- | --- |
| Does the afterimage improve timing? | no model-authored afterimage; baseline only | sensed-scope afterimage | false ignitions, duplicate calls, latency to real change, prediction error on observable fields |
| Does the baseline help? | no EMA baseline | current EMA | repeat-surprise rate, missed state changes, oscillation |
| Do node values add anything beyond prompt prose? | timing held fixed; node labels/values hidden | labels/values shown | act/reach/null distribution, schema validity, timing unchanged by construction |
| Do settling calls support continuity? | no quiet-time model call | neutral settling call | memories/makings created, cost, later recall, without treating output count as health |
| Does fervor add self-direction? | same call timing with neutral wording | current charge/discharge wording | act/reach/null distribution and semantic repetition; numeric schedule held fixed |
| Does venture improve world use without overriding choice? | ordinary verb menu | soft venture; hard venture separate | successful movement/do, blocked acts, later voluntary return, action diversity |
| Do anchors support continuity or recursion? | no anchor feedback | provenance-separated anchors; current mixed anchors separate | anchor persistence after source removal, prompt-output autocorrelation, false ignition |
| Does identity resonance preserve distinctness? | no resonance block/ranking | resonance block only; chatter ranking separate | cross-resident similarity, within-resident continuity, place-choice concentration |
| Do stock examples homogenize behavior? | schema only | varied examples; shared example separate | structural act distribution and offline term concentration |
| Does memory retrieval help? | recency | relevance; relevance-plus-diversity separate | later correct use of seeded facts, retrieval concentration, duplicate keeps |

No arm should be judged by “talked more,” “moved more,” or “made more” alone.

## Fourth: rename before theorizing

Once the causal paths are clean, names should describe computation:

- `arousal` → `call_pressure` unless a stronger mapping is demonstrated;
- `ignition` → `pulse_threshold_crossing` or `model_call_opened`;
- `social_pull` → separate `unseen_direct_address`, `unread_mail`, and `recent_contact` fields;
- `withdrawn` → `no_current_social_signal`;
- `grief` → `predicted_anchor_absence_integral` while experimental;
- `vital/distress/strangled` → `call_delivery_status` and `above_threshold_without_completion`;
- `owes_reply_to` → `unanswered_direct_address_from` only while actually unanswered;
- `felt_sense` → `model_self_report` in code/telemetry, while the resident-facing label may remain humane.

Plain names do not settle philosophical questions. They stop the implementation from claiming an answer it
does not have.

## Literature order

External literature should answer bounded questions after the software corrections:

1. What parts of predictive-processing accounts are empirically distinguishable from feed-forward or simpler
   control models?
2. What does global-workspace or ignition research actually establish, and at what implementation level?
3. What evidence exists for arousal-performance relationships across task, person, and context rather than one
   monotonic scalar?
4. What do ecological and enactive accounts require from a body/environment coupling that this HTTP world does
   or does not provide?
5. What can phenomenology and contemplative reports contribute as disciplined descriptions without being
   converted into proof about this software?
6. What ethical and disability-aware work warns against treating silence, slow response, solitude, repetition,
   or non-productivity as dysfunction?

Only then should a decision document say which metaphors remain useful and which mechanisms merit another
implementation.
