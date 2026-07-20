# Model authorship, self-feedback, and dead pulse fields

Status: code audit, 2026-07-19. No live resident prose was read for this pass.

## Plain result

One `Pulse` currently mixes several different jobs into one model-generated JSON object:

- choose a private information source;
- choose one outward action;
- describe an inner feeling;
- predict what will happen next;
- select a durable memory;
- propose an identity change;
- propose a goal or reverie;
- create a temporary drive;
- judge the traces that opened the model call.

Those fields do not have equal authority. An `act` can change the world. An expectation can change when the
model is called again. A keepsake enters future prompts. A `soul_edit` can become identity only after a later,
explicit adoption. Other fields are merely written to the ledger and never read again.

This is a central source of the runtime's hand-wavy complexity. The schema makes several unfinished designs
look like one complete cognitive mechanism. It also makes every model call spend tokens and attention on
outputs that have no effect.

## What each model-authored field can actually do

| Field or output | Immediate destination | Later reader | Actual authority |
| --- | --- | --- | --- |
| `reach` | private information provider | continuation call in the same activation | selects information inside a host-opened, bounded reading window |
| `act` | world effector | world state, public events, and some later perception paths | proposes the one outward action for the activation |
| `expectations` | `afterimage_cast` ledger events | surprise and prompt construction | directly changes later call pressure and prompt content |
| `felt_sense` | `felt_sense_logged` ledger event | elective recall and automatic anchor extraction | automatically feeds model self-description back into future context; optional anchor gating can also affect call timing |
| `keep` | ledger plus `kept_memory.jsonl` | later prompts, recall, and incubation count | automatically creates durable selected memory after one model response |
| `self_delta.soul_edit` | accepted candidate event | private growth source and exact adoption action | proposes identity text; it changes identity only after later inspection and adoption |
| `self_delta.new_reverie` | accepted candidate event | none found | dead record |
| `self_delta.goal_update` | accepted candidate event | none found | dead record |
| `drive_nudges` | decaying ledger events | reducer exists, but no production caller found | dead record with unused decay machinery |
| `trace_verdicts` | verdict ledger events | none found | dead record |
| successful speech | world plus resident ledger | optionally the voice-register system prompt | public action; under one flag, also recursive style instruction |
| workshop write | private artifact file plus ledger receipt | automatically summarized into every later prompt | durable private work that becomes unavoidable recurring prompt context |

This table should become a maintained contract, not an audit-only reconstruction. No model output should be
added to the pulse schema until its storage, reader, authority, expiry, failure behavior, and tests are named.

## The pulse object crosses too many boundaries

The schema asks one model response to report what a moment feels like, predict the future, choose an action,
decide what becomes memory, and propose who the resident is becoming. These are not merely different JSON
fields. They are different kinds of decision:

- **world control:** an action request;
- **information control:** a private read request;
- **scheduler control:** expectations that change later surprise;
- **telemetry or self-description:** a felt report;
- **long-term continuity:** a keepsake;
- **identity governance:** a proposed soul edit;
- **unfinished research ideas:** drives, reveries, goals, and trace verdicts.

Combining them hides policy choices. For example, the outward action is strictly validated so malformed input
can cancel the whole pulse. Most inner arrays are softly parsed and malformed entries are silently dropped.
That is reasonable if they are optional decoration. It is not a reliable basis for claiming that the ledger
contains complete predictions, memories, or metacognitive judgements.

The prompt also says `self_delta` is “rare and slow,” but code imposes no rarity, rate, or proposal limit. A
model may stage a soul edit on every call. The later adoption boundary prevents automatic identity mutation,
but the live prompt still manufactures an unlimited candidate stream.

## Reaching gives the first response conditional authority

An activation may contain several model calls. When the first response requests information, `_reach_then_act()`
passes only the request and its `felt_sense` into the continuation. When that continuation succeeds, the next
full `Pulse` replaces the previous one and only the final pulse is routed.

When the continuation fails, the read budget is zero, the information boundary is unavailable, or a read is
deduplicated, the implementation instead strips `reach` from the earlier pulse and routes all its other fields.
Initial expectations, keepsakes, self changes, drive nudges, and trace verdicts are therefore provisional on a
successful continuation but become durable on several failure paths. The contract explains neither behavior.
It asks for the whole object on every continuation.

Routing only the final decision can be a sound transaction boundary. The interface should say so and avoid
requesting fields that cannot commit yet. A cleaner episode would have:

1. zero or more read requests;
2. one final response containing an optional act and whichever durable fields are deliberately retained;
3. one typed routing receipt.

## Four fields are decorative machinery

### Drive nudges

The prompt's default schema example advertises a temporary `curiosity` drive. The runtime stores those model-
generated features with half-lives and has a reducer that can calculate their decayed value. No production
code calls that reducer.

`CognitiveCore` has a `clean_drive_nudges` constructor argument intended to show an empty schema example, but
`Resident._build_core()` never supplies it. Normal residents therefore receive the misleading curiosity
example by default. The nearby source comment still says the nudge is read back into a self-reinforcing loop;
that describes an older or intended path, not the current code.

The result is worse than a simple unused variable: the model is invited to invent temporary drives, the
ledger records them with biological-looking decay metadata, tests confirm that decay math works, and nothing
uses the answer.

### New reveries and goal updates

`constitution_gate()` accepts `soul_edit`, `new_reverie`, and `goal_update` using the same `self_delta_staged`
event. Its documentation says every accepted edit becomes a candidate for the mature growth pipeline. Only
accepted `soul_edit` events are read by that pipeline. Reveries and goals are not adopted, surfaced, resumed,
completed, expired, or otherwise consumed.

The old research material contains elaborate reasoning about when goals or reveries should influence identity,
but the live software does not implement that policy. Tests currently preserve the event-writing behavior,
not a causal mechanism.

### Trace verdicts

Every prompt says to judge traces as `consolidate`, `release`, or `watch`. The verdict is recorded and then
ignored. It does not remove a trace, change later attention, consolidate memory, or keep something under
review. The language model is doing paperwork for a reader that does not exist.

### What to do with them

Remove these four surfaces from the live contract, data classes, routing, reducers, and tests. If a future
design needs one of them, reintroduce it as a small end-to-end feature with an explicit resident-visible
lifecycle. Do not keep a dead field merely because the name points toward an appealing future idea.

## `felt_sense` is automatic self-feedback, not a passive report

The contract says the felt report is “never acted on.” The runtime contradicts that statement:

1. every final pulse stores a model-written felt report;
2. the recall source can return these reports even when they were not deliberately kept;
3. every tick automatically mines the latest ten reports for noun phrases;
4. those phrases are mixed with current public names to produce “anchors”;
5. anchors are shown in later reactive prompts;
6. when anchor gating is enabled, selected anchors can also alter surprise and call timing.

This is a recursive language-model feedback loop. It may support continuity, or it may turn one generated
phrase into repeated evidence about the resident. The code currently cannot distinguish those explanations.

Rename the field internally to `model_self_report`, then decide separately whether it belongs in:

- private diagnostics;
- elective recall;
- automatic prompt context;
- scheduler input;
- selected memory.

Those should not be bundled consequences of writing one sentence on every call.

## Workshop work is private but not elective context

The workshop has a useful structural property: write targets are sanitized and kept inside the resident's
directory. The problem is on the read side.

Every successful perception tick calls `Workshop.summary()`. That summary includes the most recent excerpt
from every Markdown artifact and is inserted automatically into the next prompt, whether or not the resident
chose to think about the workshop. The prompt then gives detailed instructions for journaling, zines, named
projects, and SVG drawing. Settling and fervor prompts push toward the workshop even more strongly.

This creates another feedback loop:

```text
model writes project
    -> project excerpt appears in every later prompt
    -> model is repeatedly reminded and invited to write
    -> more project text appears
```

Continuity of work is valuable. Repeatedly broadcasting every current project into every waking moment is a
host policy, not elective attention. It also makes the “elective information ecosystem” incomplete: books and
world sources must be reached for, while the resident's own projects are forced into view.

There are smaller implementation mismatches:

- `summary()` reads each Markdown file once to count entries and again to parse its latest entry; its cost
  grows with every file and every appended page;
- there is no artifact-count or total-summary budget;
- `.txt` is listed as an allowed workshop type but `artifacts()` and `summary()` discover only `.md` files;
- `recent_makings`, used for the anti-repetition score, includes only the default journal plus drawing titles,
  while the prompt describes the verdict as applying to recent making in general;
- named projects and zines appear in prompt summaries but do not enter that similarity calculation.

A better boundary is a small resident-owned project index. The prompt can show project names and lightweight
status, while full excerpts are available through an elective `workshop` source or an explicitly selected
active-project slot. Reads should use bounded indexes rather than rescanning full files on every tick.

## Voice can become a recursive style loop

Voice-register prompting is off by default. When enabled, it places two kinds of samples in the system prompt:

1. host- or seed-authored `IDENTITY.md` voice examples;
2. up to three recent successful public lines from the resident's ledger.

The second group can feed population drift back into the next output. If a resident begins copying a shared
register, its own copied speech becomes stronger system-level evidence for continuing that register. The code
comments acknowledge this risk, which is why seed-only and recent-speech variants should remain distinct
experimental arms rather than one feature.

The seed format is also brittle. `IDENTITY.md` stores several quoted utterances on one comma-separated line,
and the loader uses `raw.split(",")`. A natural utterance containing a comma is therefore split into two voice
samples. The formatter then joins samples inside quotation marks without escaping quotes or newlines. This is
ambiguous prompt construction, not a trustworthy structured voice format.

There is also a separate `voice.jsonl` used by the hearth UI. It is portable and useful as a transcript, but
the cognitive voice-register path reads successful speech from the ledger instead. This is acceptable if
`voice.jsonl` is explicitly a rebuildable presentation store. It should not be described as another identity
authority.

Voice experiments should therefore use:

- structured seed samples, not comma parsing;
- a seed-only arm;
- a recent-output-only arm;
- a seed-plus-recent arm;
- an off control;
- an explicit run receipt naming the active policy.

## Identity growth is the strongest boundary in this area

The live soul-growth path deserves to survive the cleanup:

1. a final pulse may stage exact proposed text;
2. staging does not change the canonical or growth soul;
3. the resident can inspect one exact proposal through a private hearth source;
4. the resident must use the exact candidate ID in a separate hearth action;
5. adoption is written to the ledger with proposal and inspection provenance;
6. the derived identity files can be repaired after an interrupted write;
7. the next prompt and optional semantic drive see adopted text.

That is a real proposal/review/commit boundary. It should not be weakened into automatic “maturation.”

It is still incomplete:

- there is no decline, dismissal, supersession, or expiry action for a candidate;
- adopted text can only accumulate as paragraphs; there is no ordinary correction, reversal, or compaction;
- there is no proposal-rate or pending-candidate limit;
- reads and crash repair inspect only the latest 10,000 projection events, so sufficiently old pending or
  adopted records can become unreachable to these routines;
- the same model service normally proposes, inspects, and adopts the text across separate calls, so the
  software proves a deliberate lifecycle, not independent human-like judgement;
- the live route does not supply a semantic contradiction callback, and embedding similarity could not prove
  logical contradiction or that a change was “earned” anyway.

The next version should retain exact adoption while adding decline, supersession, and resident-controlled
revision. Candidate retention must be based on open lifecycle state, not an arbitrary recent-event window.

## The varied examples are not neutral

The pulse producer assigns one of six worked examples using a hash of the resident's folder-derived name.
They demonstrate different situations, tones, and actions: speaking under pressure, welcoming someone,
leaving a room, fixing an object, writing an observation, or remaining still.

This may reduce one shared example's population-wide influence, but it introduces a different confound. Two
otherwise identical residents can receive different behavioral demonstrations because an operator renamed a
folder. Calling the pool neutral does not make those demonstrations behaviorally equivalent.

For a reference runtime, use schema-only validation or one minimal example whose causal influence is measured.
If varied few-shot examples are tested, assign them as declared experimental conditions keyed to stable actor
ID, not hidden identity policy derived from a host path.

## Required code decisions before behavioral testing

1. Shrink the final pulse to fields with live, documented authority.
2. Make read-request responses a separate continuation type instead of asking for a full disposable pulse.
3. Remove drive nudges, new reveries, goal updates, and trace verdicts from the live path.
4. Rename and split the consequences of model self-report.
5. Keep the exact growth adoption boundary; add decline, supersession, reversal, compaction, and durable open-
   candidate indexing.
6. Make workshop continuity elective or explicitly selected and bounded.
7. Keep voice feedback experimental and encode seed samples structurally.
8. Stop deriving prompt examples from a resident's folder name.
9. Add a machine-checked rule: every model-authored schema field must have a named consumer, authority,
   retention rule, and end-state test.
10. Record which self-authored surfaces were active in every run without storing their prose.

These changes do not decide what a mind is. They make it possible to tell what this program does.
