# CognitiveCore calibration and design lineage

Status: first provenance pass, 2026-07-19.

This file does not ask whether a number looks reasonable. It asks why that number or mechanism exists and
what kind of evidence supports it.

## Evidence labels

- **Safety bound:** chosen to prevent a concrete software failure such as runaway output.
- **Structural choice:** one of several plausible algorithms, selected by the project.
- **Project-observed:** chosen in response to one or more WorldWeaver runs.
- **Project-calibrated:** compared against recorded project examples, but not established outside them.
- **Scientific grounding:** tied to an external empirical model closely enough that the mapping and limits are
  stated. None of the cognitive timing constants currently meet this bar.

## Numeric inventory

| Mechanism | Current values | Provenance found | Assessment |
| --- | --- | --- | --- |
| surprise filter | feature epsilon `0.02`; trace floor `0.10`; maximum feature delta | Introduced with the first salience integrator; tests pin the arithmetic | Structural choice, not biological calibration |
| arousal | five-minute half-life; threshold `1.0`; 30-second refractory period | Introduced as architecture defaults; no linked estimation record found | Hand-selected scheduler tuning |
| afterimage | ten-minute default half-life; model may override it | Introduced with the typed pulse | Hand-selected decay and partly model-authored timing |
| baseline | EMA rate `0.25`, one-minute snapshots, four-hour decay | Introduced as habituation | Hand-selected learning and decay constants |
| settling | below `0.30` for five minutes | Added because the workshop was unused when only surprise could call the model | Product/behavior intervention |
| fervor | between `0.45` and `1.0` for three minutes | Added after one resident's generated journal line was interpreted as being stuck with unused charge | Anecdote-driven intervention |
| venture | wake floor `0.40`; world-cold at five minutes; soft `0.50`; hard `0.80` | Added after a cohort produced zero move/do acts despite act-trace prompting | Project-observed output correction; hard mode directly constrains action choice |
| waveform warning | 30-minute window; 60 seconds over threshold without discharge | Added to detect failed model calls that left arousal high | Useful operational alarm with unjustified health terminology |
| absence integral called grief | prediction floor `0.20`; ten-minute half-life; felt floor `0.25`; gain `0.50`; cap `0.80` | Added during substrate port to address anchor disappearance behavior | Hand-selected experimental control term; affective label unsupported |
| anchor gate | identity similarity at least `0.50` | Added as “the price on boring” | Hand-selected experimental gate |
| anchor phrase matching | cosine at least `0.65` | Compared on one embedding model: paraphrases roughly `0.68–0.87`, distinct phrases `0.41–0.56` | Project-calibrated and model-specific |
| self-sameness | cosine at least `0.80` | Compared against one observed groove (`0.839`) and ordinary thematic examples around `0.74` | Narrow project calibration; prompt interpretation remains unsupported |
| identity slice weights | constitution `1.0`, growth `0.55`, reverie `0.35`; contradiction floor `0.12` | Introduced with drive-vector design; no estimation record found | Hand-selected semantic-ranking policy |
| incubation | four-minute floor, fifteen-minute ceiling, five grounding events | Added after several cold city cohorts converged more than warm hearth residents | Project-observed but confounded onboarding intervention |
| ambient pressure | person `0.25`; event `0.30`; trace `0.55`; weather `0.40–0.85` | No linked calibration record found | Authored simulation policy |
| social pressure | question `1.0`; request `0.8`; inbox/thread formulas | No linked calibration record found | Authored social-response policy |
| circadian rhythm | cosine peak 15:30; `0.25` wake floor; exponent `1.4`; name-hashed ±3-hour chronotype | Introduced to make the town quieter and more reflective after dark | Human-like clock simulation, not an individual biological model |
| private read cap | two continuations by default; hard ceiling eight | Added after tracing cost and unbounded same-pulse reading | Safety/operational bound, explicitly not a claim that two reads are cognitively healthy |
| model output cap | 4,000 tokens | Raised after valid SVG/long JSON output was truncated | Safety bound against runaway generation |

## What the commit history says the mechanisms were for

The commit history is unusually candid and helps separate general mechanism from desired outcome:

- **Settling** was built because an available workshop went unused. Its commit equated occasional calm output
  with giving the resident “a life of its own.” That is a product hypothesis, not evidence that silence lacked
  inner life.
- **Fervor** was built after a model-authored journal sentence was read as a complaint that arousal had “no
  door.” The chosen repair made the model write or speak from that band. One generated self-description became
  scheduler policy.
- **Self-sameness** was built after repeated themes appeared in solo runs. Its numeric boundary did receive a
  small within-project comparison, but the prompt goes further than the metric by declaring pleasure spent.
- **Act trace** was added to foreground unused verbs after writing and speaking dominated. It says variety is
  optional, but it still makes unused actions salient on a shared schedule.
- **Venture** was explicitly built to move a zero-movement metric. Hard venture chooses the action family and
  removes the writing invitation. That is scripted action pressure even though the archived design says
  outcome-specific scripting should be rejected.
- **Incubation** was built to reduce cold-start semantic convergence by withholding citywide input and
  redirecting attempted public speech into a workshop. It changes more than exposure timing: it changes where
  a chosen speech act lands.
- **Grief** was built as a fix for one failure mode in anchor bookkeeping. Its implementation is an absence
  accumulator; the emotional name arrived before any validation that the state corresponds to grief.

These histories do not make the mechanisms worthless. They mean the correct claims are narrower: each is an
authored intervention that changed or was intended to change a measured WorldWeaver behavior.

## Archived Major 49 does not match current code

The archived acceptance record says the foundational substrate is complete. Several load-bearing statements
in that record are false in the current runtime:

- it says `felt_sense` is never read back as control; current anchor extraction and recall read it;
- it says drive nudges are decaying modulations; they are stored but have no production reader;
- it says neighbor bias is plastic and strengthens with co-activation; no runtime reader applies it;
- it says affect/valence comes from the drive vector; `CognitiveCore` never supplies a `valence_fn`, so every
  surprise remains neutral;
- it says the drive uses constitution, growth, and reveries; the live builder supplies constitution and growth
  but no reveries;
- it says `self_delta` crosses a semantic constitution gate; the live core does not supply the gate callback;
- the available semantic callback is asynchronous while `constitution_gate()` calls callbacks synchronously,
  so simply passing the existing method would not implement the promised check.

The structural invariant still holds: a pulse cannot directly rewrite `SOUL.canonical.md`, and growth must be
staged, inspected, and explicitly adopted. The stronger semantic guarantee does not.

Major 49 should remain in history as the record of the architectural migration, but its completion statement
must not be used as present-tense evidence. Major 136 owns the current verification and any repairs.

## Calibration policy going forward

1. Give each constant an owner and evidence label.
2. Keep safety limits separate from behavioral targets.
3. Record the effective values and prompt-policy hashes with every run.
4. Calibrate only against an explicit failure definition; “more output,” “more movement,” and “more social
   response” are not general measures of a working resident.
5. Treat resident prose as data generated inside the intervention, not privileged diagnosis of the mechanism.
6. Prefer paired replay before live population runs when the question is causal.
7. Do not borrow biological names to stabilize arbitrary constants. Rename the mechanism to what it computes.
