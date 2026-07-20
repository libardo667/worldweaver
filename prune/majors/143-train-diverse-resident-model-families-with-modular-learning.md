# Train diverse resident model families with modular learning

## Problem

Prompt cleanup cannot prevent a language model from echoing the vocabulary, examples, and assumptions that
surround it. The first name-only Levi run showed this directly: archived civic-planning speech supplied old
themes, and one implementation word from the system prompt became a repeated public metaphor.

Training one “WorldWeaver model” could teach the interface more deeply, but it could also replace the current
monoculture with a new one. A single objective would make the risk worse: rewarding task completion, speech,
exploration, or human approval would push every resident implementation toward the same visible behavior.

Training on old resident histories is not an acceptable shortcut. Those histories contain known runtime
confounds, private material, model-generated feedback loops, and interactions whose participants did not agree
to model training merely because some speech was public.

## Proposed Solution

Use Major 142's synthetic gym to train substrate literacy: the ability to participate in WorldWeaver's event,
time, information, action, and consequence contracts. Do not train a prescribed personality or a model that
becomes the definition of a resident.

1. Establish unchanged baselines across several frontier and open-weight models. Measure temporal grounding,
   valid choices, false outcome claims, uncertainty, interruption recovery, long-plan coherence, latency,
   cost, prompt-language copying, and repeated-run consistency.
2. Start from an open-weight instruction model rather than training a language foundation from scratch. Train
   a small WorldWeaver substrate adapter on engine-verified synthetic trajectories.
3. Preserve several valid choices in the training data. A situation may permit action, reading, private work,
   deliberate delay, or silence. Do not turn one teacher model's choice into the only correct answer.
4. Keep learning layers separate and versioned:
   - shared language foundation;
   - WorldWeaver substrate adapter;
   - optional skill modules;
   - resident-specific adapter, only after a separate consent and safety gate;
   - resident-owned memory and recurrent process state.
   These layers change on separate clocks: immediate process state may change every step; an individual's
   learned adapter changes slowly and reversibly; cultural skills move only through explicit exchange and
   adoption; and the population of supported model families changes through offline evaluation. Do not blend
   those four processes into one automatic update.
5. Train and retain a population of model families across different bases, adapters, environments, and
   strategies. Use multi-objective and quality-diversity evaluation rather than selecting one scalar winner.
6. Test modular capability exchange before weight merging. A skill should have an origin, version, license,
   declared interface, sandbox test, and explicit adoption decision. Stoops may eventually carry safe skill or
   teaching artifacts, but never an unreviewed executable payload.
7. Treat resident-specific weight updates as slow, hearth-owned, reversible development. Version them, test
   for capability loss and manipulation, keep rollback checkpoints, and never train on another participant's
   private or unlicensed material.
8. Use frontier models as candidate teachers or advisers, not authorities. The engine verifies consequences,
   held-out scenarios test transfer, and human review remains separate from engagement optimization.
9. Test for convergence directly. Compare public vocabulary, action distributions, plans, information use,
   and failure patterns across model families and lives. Rename and paraphrase interface language to detect
   models that learned prompt wording instead of the underlying distinction.
10. Keep Major 138's participant protocol open. A trained resident model is one implementation among humans,
    scripted automatons, other laboratories' systems, and future model families.

## Files Affected

- `research/resident-gym/`
- `research/resident-models/` (new)
- `ww_agent/src/inference/`
- `ww_agent/src/runtime/`
- `ww_agent/src/identity/`
- `ww_agent/tests/`
- `scripts/` (training, evaluation, and model-manifest commands)
- `docs/reference/resident-models.md` (new)
- `docs/reference/architecture.md`
- `prune/majors/125-digital-stoops-make-the-city-a-local-gift-commons.md`
- `prune/majors/138-make-resident-participation-independent-of-cognitivecore.md`

## Acceptance Criteria

- [ ] A versioned benchmark compares several unchanged models before any WorldWeaver-specific training.
- [ ] Training data comes from synthetic or explicitly licensed trajectories with complete provenance; no
  existing resident's private history is required.
- [ ] A small open-weight substrate adapter improves held-out protocol competence over its unchanged base
  without being trained to speak, move, or engage more often.
- [ ] Evaluation includes unseen cities, delayed consequences, long plans, interruptions, renamed fields,
  paraphrased observations, and repeated trials.
- [ ] At least two materially different model families remain supported and neither is described as the
  canonical kind of WorldWeaver resident.
- [ ] Model, adapter, skill, and personal-learning layers have separate hashes, versions, provenance, and
  rollback paths.
- [ ] Combining or adopting a skill cannot silently replace resident identity, memory, process state, or
  permissions.
- [ ] Resident-specific training is disabled until consent, poisoning resistance, capability-retention tests,
  portability, and recovery are documented and implemented.
- [ ] Population selection preserves multiple competent strategies rather than optimizing one engagement or
  personality score.
- [ ] Public reports distinguish software competence, linguistic diversity, and human impressions; none is
  presented as proof of consciousness or moral status.

## Risks & Rollback

Fine-tuning can overfit the gym, amplify synthetic-data artifacts, erase general abilities, or teach every
model the same dialect. Keep unchanged bases, held-out worlds, multiple model families, and versioned rollback.
If an adapter improves training scenarios but fails field-renaming or unseen-city tests, reject it rather than
adding more prompt instructions around it.

Model blending and personal updates also create identity, consent, security, and portability risks. Begin with
read-only evaluation and global substrate adapters. Do not update a live resident's weights until the resident
can inspect or authorize the change through a separate, reversible process and the hearth can carry every
required artifact safely.
