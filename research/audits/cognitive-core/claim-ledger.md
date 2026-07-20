# CognitiveCore claim ledger

Status: initial inventory. “Unreviewed” means no conclusion has been reached.

| Term or claim | Concrete implementation | Current classification | Main audit question | Evidence status |
| --- | --- | --- | --- | --- |
| perception | A scheduled HTTP scene/chat/mail/grounding poll plus prompt selection | engineering mechanism with biological wording | What relevant world changes can be lost, delayed, duplicated, or withheld? | code traced; literature unreviewed |
| cognitive substrate | Five hand-built numeric nodes derived from ledger records | project architecture and broad metaphor | Do the nodes have independent causal value beyond the prose that describes them? | code traced; ablations missing |
| prediction / afterimage | Model-authored expected feature values with exponential decay | engineering mechanism loosely inspired by prediction | Does it reduce repeat surprise in a predictable way, and does that help ecological fit? | code traced; paired replay missing |
| surprise | Largest absolute feature mismatch against max(afterimage, baseline) | engineering metric | Why maximum rather than sum, precision weighting, or another competing metric? | code traced; evidence unreviewed |
| habituation / baseline | Rate-limited EMA toward node values plus time decay | engineering mechanism with learning analogy | Does it adapt without hiding persistent harm or creating oscillation? | code traced; paired replay missing |
| arousal | Time-decayed sum of surprise plus an optional absence integral | scalar control variable with strong biological analogy | Is one scalar useful, and what alternatives explain the same timing behavior? | code traced; literature started |
| ignition | Threshold crossing that permits one model pulse | scheduler mechanism with neuroscience wording | Does the threshold cause reliable, interpretable call timing? It is not evidence of neural ignition or consciousness. | code traced; literature unreviewed |
| refractory period | Minimum delay between numeric ignitions | scheduler safety control | Does it suppress duplicates without delaying important new input? | code traced; paired timing tests needed |
| social pull | Fixed maximum over direct urgency, inbox count, and thread count | hand-built policy metric | Why should these distinct events share one axis, and why is zero called `withdrawn`? | naming concern verified |
| owes reply | Derived fact after a direct question | unsupported normative label | Replace with a descriptive pending-address fact unless a resident explicitly accepts an obligation. | code concern verified |
| rest drive | Clock-derived wakefulness and fixed fatigue/night values | simulation control with circadian analogy | Does a real clock improve continuity, and should residents have individual or nonhuman rhythms? | code traced; evidence unreviewed |
| settling | A model pulse after five quiet minutes | scheduler policy | Is quiet reflection needed, or does it manufacture output from a valid silence? | code traced; ablation missing |
| fervor | A model pulse after three minutes in a middle-high band | scheduler and prompt policy | Does this add self-direction or simply instruct output? | code and prompt concern verified |
| venture | Optional pressure toward move/do after bodily inactivity | action policy with motor analogy | Is movement resident-chosen when Python selects the mode and may remove writing? | code and prompt concern verified |
| grief | Leaky integral of predicted anchor absence | experimental metric with affective label | Can absence evidence justify this label, especially when anchors mix prompt-extracted text? | code traced; rename/redesign likely, not decided |
| drive | Embedding similarity between identity text and moment/place text | relevance heuristic with motivational wording | Does semantic similarity preserve distinct interest or amplify narrow identity stereotypes? | code traced; audit missing |
| anchor | Extracted concrete phrases from recent felt text and current structured names | text feature | Does mixed provenance cause current public language to become apparent inner fixation? | known provenance concern; tests missing |
| memory recall | Embedding similarity over resident-selected keepsakes, with recency fallback | retrieval mechanism | Does it support continuity or repeatedly retrieve one semantic attractor? | code traced; evaluation missing |
| self-sameness | Similarity of latest making to prior-making centroid | output-diversity heuristic | Why should semantic repetition mean pleasure is “spent,” and does the prompt force novelty? | prompt concern verified |
| felt sense | Model-generated free text stored in the private ledger | continuity artifact, not independent observation | What legitimate software use remains after removing phenomenological overclaim? | epistemic limit identified |
| relationship | Projection from delivered utterance and reply edges | evidence-backed relational state | Which claims stay descriptive, and which infer motives or duties not present in the evidence? | partial code audit |
| incubation | Time- and event-bounded removal of citywide chatter plus speech redirection | experimental exposure policy | Does it protect distinct development or isolate a resident through steward assumptions? | code trace pending |
| healthy / distressed mind | Arousal waveform labels based on discharge timing | unsupported health language over an operational liveness detector | Rename around call delivery and scheduler liveness unless validated for a narrower meaning. | code concern verified |
| body | Current world attachment, scene, spatial rules, and typed effectors | functional embodiment claim | What is gained and lost by calling an HTTP/world-state boundary a body? | literature started |
| working | Not currently defined in code or docs as separate axes | missing evaluation contract | Keep safety, causal effect, ecological fit, continuity, viability, and epistemic limits separate. | definition adopted for audit |

