# CognitiveCore prompt policy audit

Status: first complete classification of the live pulse prompt, 2026-07-19.

The pulse prompt is not a neutral rendering of resident state. It is also the resident's action interface, a
memory policy, a style guide, and a set of behavioral nudges. Those roles need to be named separately so a
change in behavior is not mistakenly credited to the numeric substrate.

## Classification

| Prompt block | What it contains | Classification | Main concern |
| --- | --- | --- | --- |
| `SOUL.md` | Authored identity description plus adopted growth | Identity scaffold | Strong and intentionally individual, but still authored/model-facing text rather than discovered ground truth |
| `GROUND TRUTH` | World-supplied situational statements, rendered once when the core is built | Host claims plus philosophical and memory authority | Some are accurate affordances; others are false, mutable, or stale, yet the model is told not to remember contrary evidence |
| current moment | Exact-place scene, selected speech/events, reachable places, and source catalog | Observation filtered by Python | The model sees what prompt-selection policy includes, not an unmediated world |
| act trace | Counts dominant proposed act kinds and names unused doors | Behavioral nudge built from false success semantics | It reads `pulse_act_emitted`, not outcomes, so blocked moves are described as movement and declined actions as completed history |
| memory | Relevant or recent resident-selected notes | Retrieved history | Embedding retrieval can repeatedly surface one semantic cluster; recency fallback is a separate condition |
| workshop | Prior artifacts plus detailed writing/drawing instructions | Affordance manual plus creative invitation | Present on nearly every pulse, so making is continually advertised whether or not the moment calls for it |
| self-sameness warning | Embedding similarity over recent makings | Direct anti-repetition policy | “Pleasure is spent” is not measured. The block orders novelty or rest once similarity reaches `0.80` |
| settled baseline | Recent EMA values rendered as “how you have usually felt” | Computed state rendered as self-knowledge | A short numeric history is presented as settled selfhood |
| anchors | Nouns extracted from model-authored felt text and current names | Mixed-provenance feature framed as inner attention | Public names can be described as “anchors of your inner world”; provenance is not retained per anchor |
| resonance | Identity-text fragment selected by embedding similarity | Individualized prompt nudge | May preserve voice or amplify a narrow authored stereotype; needs an ablation |
| react opener | Threshold and mismatch prose | Scheduler explanation | Tells the model it “woke” because “arousal” crossed a threshold, importing the project's interpretation into generation |
| settling opener | Quiet-world framing and permission to make or rest | Low-pressure action policy | “Nothing presses, nothing surprises” can overstate what a bounded poll established |
| fervor opener | “Wound tight,” “charge,” and “don't just sit on it” | Strong action policy | Converts a middle-range scalar into an instruction to discharge through output |
| venture opener | Pull toward a Python-ranked place; hard mode removes workshop and instructs move/do | Motor policy | At high strength the resident cannot choose writing from the advertised interface; movement is partly selected before inference |
| output contract | JSON schema and routing rules | Interface facts mixed with normative policy | “Act when addressed” turns notice into presumed response; `felt_sense` and allowed prediction scopes are described inaccurately |
| worked example | One of six stock scenes selected by a name hash | Population-level few-shot intervention | Six examples are more varied than one, but all residents still inherit the same small behavioral vocabulary and everyday scene grammar |
| voice samples | Optional authored/recent utterances | Style intervention | Off by default; when enabled, recent speech can feed a drifted shared register back into later speech |
| reach continuation | Chosen source result plus remaining sources | Information interface and provenance warning | Bounded and comparatively explicit; a second model call still re-applies the full behavioral contract and example |

## Direct pressure points

The strongest steering is not hidden in model weights. It is plain text written by the project:

- a direct address should normally produce a non-null act;
- a repeated creative theme is called worn and its pleasure declared spent;
- middle-high arousal is described as charge that wants spending;
- hard venture directs a move or physical act and withholds the workshop;
- a workshop, journal, zine, drawing surface, and stock scenes appear across the population;
- prior output is named as what the resident “feels” and what its inner world is “about.”
- proposed acts are narrated as successful behavioral history even when the world declined them.

These may be defensible game or interaction policies. They are not observations about what an agent naturally
does. A run using them cannot establish that the numeric substrate independently caused reflection, movement,
social response, or creative variation.

## Shared prompts and monoculture

The varied-example flag is on by default, but it chooses from only six examples. The pool includes:

- answering a named person in a busy workplace;
- welcoming someone back;
- leaving a close room for the docks;
- fixing a neglected latch;
- writing down a small observation;
- explicitly choosing no act.

This is a better spread than one shared reply example, but it remains a compact authored culture. The same
contract, workshop language, cognitive labels, and mode metaphors are much larger shared surfaces than the
single example. A name hash also makes example assignment reproducible, not experimental: there is no runtime
receipt saying which wording changed what behavior.

Two small quality defects reinforce the need to treat the prompt as production code:

- the Rosa example contains the `felt_sense` key twice;
- the fervor branch constructs the same `interior` string twice in succession in Python (the second assignment
  replaces the first, so the rendered prompt is not duplicated).

Neither defect explains population behavior by itself. They show that the prompt needs the same exact review,
linting, and causal tests as other policy-bearing code.

## Field-by-field contract accuracy

| Contract claim | Code truth |
| --- | --- |
| `felt_sense` is never acted on | False as written. It is not directly executed, but it feeds recall and anchor extraction and may feed arousal under anchor gating. |
| `reach` is private and never a physical act | Supported by the integrator/effector split. The result and prompt trace still live on the steward's filesystem. |
| most moments keep nothing | A prompt preference, not an enforced limit. |
| choose an act when someone addresses you | A social-response policy. Direct attention and compulsory response are separate decisions. |
| expectations become later predictions | Supported for stored afterimages, but only `self` and optional `anchors` have real observed stimulus lanes. |
| person and `here` scopes are valid | Structurally unsafe today: missing observations are treated as zero and manufacture surprise. |
| self change is rare and earned | A prompt preference. The code gate checks form/contradiction; it does not establish that change was earned. |
| give verdicts on waking traces | Accepted and stored, but current production code never uses those verdicts. |
| drive nudges are part of the resident's transient motivation | Accepted and stored, but current production code never uses them. |

## Current defaults in ordinary resident construction

- recent-act reflection: on;
- varied stock example: on;
- voice-register samples: off;
- action-tendency/venture: off unless explicitly enabled by a runner or environment;
- anchor gating: off unless enabled in resident tuning;
- incubation: off unless enabled in resident tuning or shard environment;
- clean drive-nudge schema: off, and `Resident` does not expose it when constructing `CognitiveCore`;
- elective reach continuations: host-bound default of two.

The current Alderbank tuning files contain home/landmark values and do not override anchor gating or
incubation, so their loader defaults are off. Environment values still need a run receipt to establish the
exact effective configuration of any particular launch.

## Safer ablation order

Do not begin by deciding which account of mind is correct. First make the software capable of telling us which
layer caused an outcome:

1. Render a minimal contract containing only valid schema and real affordances.
2. Remove stored-only pulse fields from that arm.
3. Restrict expectations to sensed scopes.
4. Compare no mode metaphor against current settling/fervor/venture wording while holding numeric decisions fixed.
5. Compare no workshop invitation against the current always-advertised workshop.
6. Compare no stock example, varied stock examples, and resident-specific voice examples separately.
7. Compare activation values hidden versus shown while leaving call timing unchanged.
8. Record exact prompt-policy flags and hashes with every run.

Only after those paired replays should a behavior be attributed to afterimages, baseline, arousal, identity
resonance, or another substrate mechanism.
