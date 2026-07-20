# Evidence review 01: prediction, ignition, arousal, quiet, and social norms

Status: bounded review, 2026-07-19. This review limits itself to words and mechanisms already present in the
live code. It does not attempt to prove or disprove machine experience.

## What outside evidence can and cannot do here

Evidence about humans and other animals can show that a software analogy is narrow, contested, or missing
important variables. It cannot establish that the same mechanism or experience exists in an LLM host. Every
software mechanism still needs a direct causal test against a simpler alternative.

## Prediction and surprise

Hodson, Mehta, and Smith's 2024 critical review reports modest empirical support for predictive coding,
notes that some positive findings also fit feed-forward alternatives, and calls for formal comparison of
active-inference accounts against non-Bayesian and model-free alternatives:
[DOI 10.1016/j.neubiorev.2023.105473](https://doi.org/10.1016/j.neubiorev.2023.105473).

Bowman and colleagues separately ask what would make predictive coding falsifiable and emphasize the need
for concrete patterns that a model could fail:
[DOI 10.1016/j.neubiorev.2023.105404](https://doi.org/10.1016/j.neubiorev.2023.105404).

WorldWeaver does not implement a hierarchical generative model, precision weighting, posterior inference,
or action selected to resolve prediction error. It takes the largest absolute mismatch between a few
hand-authored values and adds it to a call scheduler. The responsible conclusion is not that predictive
processing is wrong. It is that the current code should be named and tested as an engineering heuristic,
with max mismatch compared against transition events, weighted sums, novelty, and simpler timers.

## Ignition

Global Neuronal Workspace Theory uses ignition for a proposed brief, content-specific amplification and
global broadcast across interconnected brain networks. A preregistered, adversarial, multimodal study of 256
human participants found results that aligned with some predictions while substantially challenging key
parts of both GNWT and Integrated Information Theory. In particular, GNWT was challenged by a general lack
of the predicted ignition at stimulus offset and limited prefrontal representation of some conscious
dimensions:
[Cogitate Consortium et al. 2025](https://doi.org/10.1038/s41586-025-08888-1).

WorldWeaver has no neural population, global broadcast measurement, competing workspace theory, or
conscious-access outcome. Its “ignition” is a Python threshold that opens an LLM API call. Rename it
`model_call_opened` or `call_threshold_crossed`. The neuroscience word supplies no validation.

## Arousal

Aston-Jones and Cohen's adaptive-gain account distinguishes phasic and tonic locus-coeruleus modes and ties
them to task engagement, exploitation, and exploration rather than one universally beneficial rising value:
[DOI 10.1146/annurev.neuro.28.061604.135709](https://doi.org/10.1146/annurev.neuro.28.061604.135709).

Lee and colleagues found that experimentally induced arousal amplified salient information and suppressed
non-salient information in younger adults, while older adults showed amplification without the same
suppression and were more open to distraction:
[DOI 10.1038/s41562-018-0344-1](https://doi.org/10.1038/s41562-018-0344-1).

These findings do not map directly to software residents. They do establish that biological arousal is not
adequately represented by “sum mismatches, multiply by a clock curve, then spend the number through a model
call.” The current variable should be called `call_pressure`. If broader attention is desired, phasic event
notice, longer background state, action readiness, and sleep/rest policy should remain separate until tests
show a reason to join them.

## Quiet and rest

Two recent meta-analyses report a positive average association between post-learning wakeful rest and later
memory. Weng and colleagues pooled 37 studies and found a moderate overall effect, with variation by age and
outcome type:
[DOI 10.3758/s13423-025-02665-x](https://doi.org/10.3758/s13423-025-02665-x).
Parra, Zhang, and Radvansky found a smaller pooled effect with moderate-to-large heterogeneity, a prediction
interval that included negative effects for future studies, and substantial differences among participant
groups and task designs:
[DOI 10.3758/s13423-025-02778-3](https://doi.org/10.3758/s13423-025-02778-3).

This is not evidence that an inactive LLM consolidates memory between calls; it does not. It is strong reason
not to define outward silence or lack of fresh text as dysfunction. If WorldWeaver wants an analogue of
consolidation, it needs an explicit, measurable software process such as cache rebuilding, memory indexing,
or later retrieval improvement. A forced “settling” inference every five minutes is additional processing,
not demonstrated rest.

## Social behavior and deficit assumptions

Rifai and colleagues found that familiar non-autistic signals such as mutual gaze and backchanneling related
differently to rapport across non-autistic, autistic, and mixed-neurotype pairs. Lower use did not imply lower
rapport in autistic pairs:
[DOI 10.1089/aut.2021.0017](https://doi.org/10.1089/aut.2021.0017).

Crompton and colleagues found that information transfer along autistic-only chains did not significantly
differ from non-autistic-only chains, while mixed chains lost more detail:
[DOI 10.1177/1362361320919286](https://doi.org/10.1177/1362361320919286).

The narrow lesson for WorldWeaver is methodological: communication success is relational and context-bound.
A low value on one project's preferred social behavior cannot safely be labeled `withdrawn`, and a delayed
or absent reply cannot by itself establish distress, incapacity, or failed personhood. Measure delivery,
mutual understanding, accepted commitments, and world consequences separately.

## Decisions supported by this first review

- Keep prediction, timing, memory, and attention as testable engineering mechanisms.
- Remove neuroscience and health authority from their runtime names and operator displays.
- Treat quiet, repetition, solitude, reading, delayed response, and non-action as valid outcomes.
- Require a neutral reference runtime and paired causal tests before restoring a behavioral intervention.
- Evaluate social behavior at the relationship and environment level, not as an individual deficit score.
- Keep philosophical and first-person questions open; none of these sources settles them.
