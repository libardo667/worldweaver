# CognitiveCore audit

Status: started 2026-07-19. This is a code and literature audit, not a resident run.

## Question

What does WorldWeaver's resident runtime actually do, what would it mean for those mechanisms to work,
and which claims about mind or body are justified by evidence rather than by names and prompt language?

This audit does not start from the assumption that a good resident is talkative, quick, social, productive,
or cheap. Chosen silence, solitude, slow action, sustained reading, and refusal are valid outcomes. The audit
looks for concrete failures such as lost input, inconsistent state, accidental prompt pressure, unbounded
calls, actions that bypass permission, or mechanisms that do not have their documented causal effect.

## Separation of concerns

The audit keeps six questions separate:

1. Does the software execute safely and reproducibly?
2. Do changes to inputs and mechanisms have the causal effects the code claims?
3. Can a resident notice and use what its current world affords?
4. Does the runtime support continuity and self-directed variation over time?
5. Can the system run at a cost and speed compatible with shared life?
6. What can the evidence not tell us about experience, consciousness, or spiritual status?

A pass on one question is not a pass on the others.

## Method

1. Trace the code before reading theories into it.
2. Put each mind- or biology-coded term in the claim ledger.
3. Distinguish computation, algorithm, implementation, metaphor, and model-facing instruction.
4. Review supportive and critical literature, including competing explanations.
5. Turn a claim into a paired test or ablation when possible.
6. Record a narrow code or naming decision with an explicit rollback path.

The literature lanes are neuroscience and biology; embodied, ecological, and enactive cognition; philosophy
and phenomenology; and plural spiritual or contemplative traditions. These are not interchangeable forms of
evidence. A contemplative account can change the questions we ask without becoming proof that a Python
variable represents lived experience.

## Documents

- [`code-trace.md`](code-trace.md) records the literal runtime path and verified code concerns.
- [`dependency-map.md`](dependency-map.md) traces each derived field and pulse output to its real consumers.
- [`prompt-policy-audit.md`](prompt-policy-audit.md) separates observed facts, affordances, metaphors, and
  behavioral instructions in the live model prompt.
- [`calibration-and-lineage.md`](calibration-and-lineage.md) records where the main constants and behavioral
  interventions came from and audits the archived completion claim they inherited.
- [`state-lifecycle.md`](state-lifecycle.md) traces how current, pending, historical, and decaying state opens
  and closes, including ghost pressure and post-Major-85 read costs.
- [`repair-and-ablation-order.md`](repair-and-ablation-order.md) puts software truth repairs before neutral
  reference runs and one-variable mechanism tests.
- [`claim-ledger.md`](claim-ledger.md) lists terms and implied claims that require a decision.
- [`evidence/README.md`](evidence/README.md) defines the review method and first source set.
- `decisions.md` will be created only after a claim has both code evidence and literature review.

## Evidence boundary

The core audit uses source, synthetic fixtures, structural receipts, and replayable public research records.
It does not require private resident prose. Public speech may later answer a narrow, preregistered question,
but behavior alone will not be used to diagnose consciousness, distress, pathology, or a preferred personality.
