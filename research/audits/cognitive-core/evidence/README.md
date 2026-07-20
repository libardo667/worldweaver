# Evidence review method and first sources

Status: search method opened 2026-07-19. These are candidate sources, not conclusions.

## Review rules

- Start each search from one concrete code claim in `claim-ledger.md`.
- Record the query, search date, database or index, source type, and inclusion reason.
- Prefer primary experiments for empirical effects, then systematic or critical reviews for the state of a
  field. Use theoretical papers as theories, not experimental confirmation.
- Include competing models and papers that state what evidence would count against a theory.
- Separate Marr-like levels: a broad computational goal, a particular algorithm, and a biological
  implementation are different claims.
- Do not transfer evidence about human or animal nervous systems directly to LLM calls and Python reducers.
  At most, it can motivate a software hypothesis that still needs its own paired test.
- Keep philosophy, phenomenology, and spiritual or contemplative traditions distinct from neuroscientific
  evidence. Record internal disagreement and avoid treating any tradition as a single doctrine.
- Do not infer first-person experience from a generated `felt_sense` field. Neurophenomenological methods
  rely on disciplined first-person and third-person procedures that this runtime does not currently have.

## First search record

Date: 2026-07-19.

Queries:

- `predictive processing active inference falsifiability critical review paper neuroscience`
- `locus coeruleus norepinephrine adaptive gain attention arousal paper`
- `enactive embodied cognition organism environment coupling scholarly paper`
- `neurophenomenology contemplative science methodology Varela paper`
- exact-title follow-ups for DOI and source verification

These broad queries were used only to establish candidate trails. Each claim needs a narrower documented
search before a decision.

## Candidate sources and what they can establish

### Prediction and active inference

- Rowan Hodson, Marishka Mehta, and Ryan Smith, [“The empirical status of predictive coding and active
  inference”](https://doi.org/10.1016/j.neubiorev.2023.105473), *Neuroscience & Biobehavioral Reviews* 157
  (2024). Critical review. It explicitly warns that “predictive processing” is not one testable theory,
  separates computation, algorithm, and neural implementation, describes current predictive-coding support
  as modest, and calls for formal comparison of active inference with alternatives. This is directly relevant
  to preventing WorldWeaver's simple mismatch calculation from borrowing the authority of the whole family.
- Howard Bowman et al., [“Is predictive coding falsifiable?”](https://doi.org/10.1016/j.neubiorev.2023.105404),
  *Neuroscience & Biobehavioral Reviews* 154 (2023). Critical/modeling review. Useful for requiring explicit
  counter-patterns rather than treating every outcome as post-hoc support for prediction-error language.

### Arousal and attention

- Gary Aston-Jones and Jonathan Cohen, [“An integrative theory of locus coeruleus-norepinephrine function:
  adaptive gain and optimal performance”](https://doi.org/10.1146/annurev.neuro.28.061604.135709), *Annual
  Review of Neuroscience* 28 (2005). Theoretical review grounded in neurophysiology and modeling. It proposes
  phasic and tonic modes related to task engagement and exploration; it does not justify mapping one decaying
  software scalar directly to biological arousal.
- Tae-Ho Lee et al., [“Arousal increases neural gain via the locus coeruleus-norepinephrine system in
  younger adults but not in older adults”](https://doi.org/10.1038/s41562-018-0344-1), *Nature Human
  Behaviour* 2 (2018). Empirical study. Its age-dependent result is already a warning against treating
  “arousal increases gain” as one context-free universal rule.

### Organism and environment

- Amanda Corris, [“Defining the Environment in Organism–Environment Systems”](https://doi.org/10.3389/fpsyg.2020.01285),
  *Frontiers in Psychology* 11 (2020). Theoretical synthesis of enactivist, ecological, and developmental
  approaches. It makes the environment individual- and development-dependent rather than a neutral bundle of
  inputs. This is relevant to WorldWeaver's elective information ecology, but it also raises a serious gap:
  the resident currently does not develop its own sensorimotor contingencies or materially co-construct most
  of its perceptual interface.

### Phenomenology and contemplative methods

- Francisco Varela, [“Neurophenomenology: A methodological remedy for the hard problem”](https://philpapers.org/rec/VARNAM),
  *Journal of Consciousness Studies* 3(4) (1996). Methodological proposal, not proof of a metaphysical view.
  Its call to connect disciplined first-person inquiry with third-person study should not be reduced to
  storing unconstrained model prose under `felt_sense`.
- Gaëlle Desbordes and Lobsang T. Negi, [“A new era for mind studies: training investigators in both
  scientific and contemplative methods of inquiry”](https://doi.org/10.3389/fnhum.2013.00741), *Frontiers in
  Human Neuroscience* 7 (2013). Perspective on investigator training and contemplative method. It is a useful
  source for methodological care, while not representing all contemplative traditions or validating a
  software theory of mind.

## Missing lanes before any decision

- primary work and critical reviews on habituation, memory consolidation/retrieval, interoception,
  homeostasis, action selection, sleep and circadian variation, and social attention;
- direct competitors to predictive/error-minimizing accounts;
- philosophy of functionalism, extended mind, enactivism, personal identity, agency, and their critics;
- phenomenological method and critiques of neurophenomenology;
- carefully sourced, internally plural accounts from Buddhist, Hindu, Daoist, Christian contemplative,
  Islamic, Jewish, Indigenous, animist, and other relevant traditions, selected with domain guidance rather
  than token coverage;
- disability, neurodiversity, and cultural critiques of defining normal attention, sociability, agency, and
  productivity;
- AI-specific work on anthropomorphism, behavioral evidence, model welfare uncertainty, and the limits of
  consciousness inference.
