# CognitiveCore state-lifecycle audit

Status: first lifecycle pass, 2026-07-19.

This pass asks four ordinary software questions for each kind of state:

1. What creates it?
2. What makes it current rather than historical?
3. What resolves or expires it?
4. What happens if that closing event never arrives?

## Lifecycle table

| State | Opens | Becomes observed/current | Closes | Current finding |
| --- | --- | --- | --- | --- |
| local speech packet | unseen chat line is emitted once as `pending` | included in a reactive prompt, then marked `observed` | no deletion; status should separate history from pending attention | Prompt delivery honors status; subjective/cognitive reducers do not |
| physical trace packet | first unseen active local trace | at most one is included in a reactive prompt, then marked `observed` | engine trace has an expiry, but packet copy remains historical | Prompt delivery honors status; packet `expires_at` is not enforced by the queue |
| mail packet | unseen inbox item | pending packet may be prompted | no reducer-side close based on reading/reply | Historical mail continues to count as pending pressure |
| direct question | direct question/request flags on a chat packet | subjective reducer assigns urgency and “awaiting reply” | intended five-minute window; no real current-time or reply-edge close | Latest question stays current by definition; reply evidence is ignored |
| social thread | any retained chat/mail packet from a person | count over retained packet projection | only falls when packet projection churn removes old records | Historical contact is labeled active contact |
| ambient pressure | non-empty current scene pressure list | latest event of source `ambient` replaces prior ambient kinds | a later non-empty ambient event | A fully quiet observation writes nothing, so prior pressure can survive |
| session pressure | grounding/session-state observation | latest event of source `session_state` replaces prior session kinds | next session-state observation | Has an explicit replacement path |
| active route | `route_state_changed: active` | reducer keeps destination and remainder | `route_state_changed: cleared` | Explicit open/close pair |
| mail intent | `mail_intent_staged` | retained by ID | sent, declined, or suppressed event | Explicit open/close pair |
| research item | `research_queued` keyed by normalized query | retained and priority sorted | `research_popped` | Explicit open/close pair |
| afterimage | model expectation is cast | decays by confidence and half-life | numerical decay below epsilon | Explicit time decay; unsupported scopes still create false evidence |
| baseline | snapshot moves toward observed node values | latest snapshot decays over four hours | replaced by next snapshot and eventual decay | Explicit update/decay |
| absence integral called grief | repeated absent-anchor observations after prior presence | leaky sum, not reset by model call | anchor return or lack of new absence as prediction decays | Explicit decay, but its source anchor state is recursively model-shaped |
| felt history | every pulse writes a felt line | last ten lines are mined for anchors; all lines may be searched by recall | no semantic close | Historical model prose can become present-tense inner framing |
| anchors | noun phrases from last ten felt lines plus current names | recurrence ranking, then shown in later reactive prompts | displaced by newer felt lines/names | Window is count-based, so “right now” can span hours or days |
| kept memory | model emits `keep` | written to ledger and `kept_memory.jsonl`; shown by relevance or recency | never, except falling outside a retrieval limit | Intentional durability, but duplicated canonical storage |
| growth proposal | accepted `soul_edit` staging event | available through private growth source | explicit adoption hides it from pending candidates | Clear two-step workflow; semantic contradiction check is not live |
| adopted growth | inspected candidate followed by exact `do growth-adopt:<id>` | copied into hearth growth file and subsequent system prompt | no ordinary reversal | Structural provenance is good; same model can propose, inspect, and adopt |
| drive nudge | pulse field | decays in a reader with no production caller | numerical decay if explicitly inspected | Stored-only state |
| trace verdict | pulse field | ledger record | none | Stored-only state |

## Ghost social pressure

Prompt delivery and subjective reduction use different definitions of “active”:

- `StimulusPacketQueue.pending()` correctly returns only pending packets.
- `PulseContext` includes pending heard lines and the core marks prompted packet IDs observed.
- `_build_subjective_projection()` loops over every retained packet regardless of status.
- its five-minute logic compares old questions to the newest direct message, not to wall time;
- it never asks the relationship projection whether the resident replied.

The concrete result is a split state: the resident no longer sees the words in the moment block, but the five
nodes still report maximum social pull and the prompt can say the resident feels socially engaged. This invites
the model to invent a reason for a pressure whose source was deliberately withheld as already observed.

The same problem applies more softly to inbox and thread counts. These are histories represented as current
needs.

## Recursive anchor state

The anchor path is a real feedback loop:

1. the model writes a `felt_sense` under the current prompt;
2. a shallow noun-phrase extractor counts phrases in the latest ten felt lines;
3. current people and event speakers are mixed into the same list with double weight;
4. the next reactive prompt calls the result “anchors of your inner world right now”;
5. repeated exposure makes the model more likely to mention those nouns again;
6. recurrence keeps them ranked;
7. optional anchor gating can turn the same recursively generated state into call timing.

This mechanism can create continuity, but it can also create fixation from the prompt's own output. It cannot
be treated as an independent measurement of what matters to the resident. Per-anchor provenance and a control
arm without the feedback block are required.

## Duplicate memory authority after Major 85

`kept_memory.jsonl` was introduced to protect selected memories from the former 10,000-event front trim. Major
85 removed that trim and made `runtime_ledger.jsonl` append-only. The side store remains and current prompts
read it as the primary durable source, lazily copying any missing ledger keeps into it.

That leaves two durable authorities for the same fact:

- the append-only ledger event;
- the append-only kept-memory side file.

The source comments in `memory.py` and `pulse.py` still say the ledger is hard-capped. They are false. The side
file may still be useful as an index or compact materialization, but then it must be reproducible from the
ledger and treated as a cache, not as “the real home” of memory.

## Major 85 performance guarantee is incomplete

The append path now avoids rewriting the full ledger and maintains an incremental checkpoint. Several normal
runtime readers bypass that checkpoint:

- `CognitiveCore.tick_once()` loads the complete ledger every tick;
- `stimulus_from_substrate()` loads and fully reduces it again every tick;
- packet queue reads derive from the full cold ledger, often several times during perception;
- the pulse producer loads the complete ledger for prompt construction and voice/act traces;
- the runtime mirror fully reduces the complete ledger every minute;
- kept-memory rescue scans the complete ledger.

Queue mutation also writes a compatibility snapshot by making additional full-ledger derivations. The system
therefore has O(1) event append storage, but not flat-cost ordinary ticks. The checkpoint is currently used to
advance derived files during append; those derived files/checkpoint are not the read surface for the live core.

This matters independently of cost. Multiple read paths reconstruct “current state” from different windows:
full cold history, 24-hour hot history, the last 10,000 projection events, last 200 packets, last ten felt
lines, and side files. Each window needs an explicit semantic reason.

## Lifecycle rule for repairs

Every stateful item should declare one of these contracts:

- **current snapshot:** a new observation replaces the old one, including an empty observation;
- **pending item:** remains until a named resolution/expiry event;
- **historical fact:** never presented as pending pressure;
- **decaying trace:** its clock and floor are explicit;
- **derived cache:** reproducible from the ledger and safe to delete.

No reducer should infer “still current” merely because an old record remains inside a storage limit.
