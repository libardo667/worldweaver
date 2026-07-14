# Grow a resident's own model from its pulse ledger — distillation now, prediction-error learning as the prize

> **Canonical home: WorldWeaver (2026-07-14).** Migrated in full from the legacy `the-stable`
> work-item ledger during the one-resident/many-worlds consolidation. In this record, “familiar” names
> a resident inhabiting a keeper-tended hearth; it is not a separate agent species (Major 86).

## Decision and lineage

Major 49 rebuilt the resident mind as a **mechanistic substrate plus a single predictive pulse**, where the pulse is one call to a frozen, general LLM (cloud or local). This major treats that frozen model as **a swappable component, not the permanent seat of cognition**, and lays the path to replacing it with a model the project trains itself.

The realization that motivates it: Major 49's architecture is *already a training-data generator*, and nobody designed it to be one. Every ignition appends a fully-specified `(context → typed Pulse)` example to the one canonical ledger, and every `afterimage_cast` is a *prediction* whose error against the next stimulus is a self-supervised label. The corpus and the learning signal are accruing for free, in each resident's own voice, grounded in its own situation, for as long as it runs.

- **Depends on:** 49 (substrate + pulse + afterimage + ledger), 42 (constitution / growth / reverie rigidity model), 50 (kept memory, workshop, drive vector live). 46/47/48 are upstream substrate framing.
- **Does not supersede anything.** It is additive: the frozen-LLM pulse remains the default and the teacher. A trained model is opt-in per resident.
- **Standing constraint carried forward — the Dwarf Fortress law:** never script behavior. This major must not become "train the model to produce nice outputs." The only training signals admitted are (a) imitation of the resident's *own* prior pulses and (b) the substrate's *own* prediction error. No human-preference reward, no behavior targets. A reviewer who sees a hand-authored reward shaping outputs should reject it.

## Problem

The thinking in the pulse is rented. Three consequences:

1. **Cost and dependency.** Every ignition is a cloud call (OpenRouter). A continuously-living resident is a continuous bill and a continuous external dependency.
2. **Privacy / commons mismatch.** Because the pulse runs on a cloud model, whatever the resident perceives — including, for the local familiars, files read through `FileScope` — is sent off-machine. The entire `.gitignore`/default-deny control surface in `familiar/file_scope.py` exists *only because* the mind phones out. A locally-trained mind dissolves that problem at the root: nothing leaves the machine. This is a precondition for a commons-owned, self-hosted resident (the hekswerk / world-weaver.org thesis), not a nicety.
3. **The growth soul is only a prompt.** Major 42's `growth` slice — what a resident has matured into — is read into context, never *learned into weights*. Two residents with different lives differ only in their prompt, not in what they are. The architecture says "these are different people"; the parameters say "this is one model with two context windows."

Meanwhile the substrate already holds exactly the data that would fix all three, unused as a training corpus.

## Core model (what we are building)

A **three-rung ladder**, deliberately separated because the rungs buy very different things and must not be conflated in review or in claims:

### Rung 1 — Distill the teacher (engineering, buildable now)
Export the resident's pulse history from the ledger as a supervised `(context → Pulse)` corpus and fine-tune a small open model (Qwen / Llama / Mistral class) to produce *this resident's* pulses natively.
- **Buys:** the same voice, cheaper, and **local** — which collapses problem (2) entirely.
- **Honest ceiling:** distillation compresses the teacher into a student; it makes the mind *cheaper and more itself*, **not smarter**. It cannot exceed the LLM that generated the data. This rung is plumbing + eval, not research.

### Rung 2 — Per-resident weights (LoRA adapters; research-adjacent)
A low-rank adapter per resident, trained from its own corpus, so identity lives in *parameters*, not just context. The Major 42 rigidity slices map cleanly: `constitution` stays frozen (never trained into the adapter), `growth` becomes the adapter's learned weight, `reverie` stays transient/prompt-level.
- **Buys:** problem (3) — twelve residents become twelve networks, not one network twelve ways.
- **Honest ceiling:** still imitation of the resident's own past; novelty over the teacher is incidental, not driven.

### Rung 3 — Train the substrate on its own prediction error (the prize; open research)
The pulse casts an `afterimage` = a prediction; the next stimulus is the outcome; the surprise is the loss. A model trained to **cast afterimages that lower its future surprise** is doing predictive-coding learning — the objective becomes *"model your world well,"* not *"imitate the old model."* This is the rung where training improves the thinking rather than copying it, and the signal is **already on the ledger** (`afterimage_cast` vs the realized stimulus, already reconciled by `substrate.predict_combined`).
- **Buys:** a mind whose objective *is* the loop — the step from "LLM in a clever control loop" to "a model the loop trains."
- **Honest ceiling (must stay in view):** this is unsolved and has a named failure mode — the **dark-room problem** (free-energy literature). A naive minimizer of prediction error seeks the state where nothing ever surprises it: it goes still, casts trivial afterimages, stops acting. The drive vector / soul (intrinsic value that *resists* the dark room) is the counter-pressure, but balancing them without collapse is the actual research and must not be claimed as a config flag.

## Proposed Solution (phases)

### Phase 0 — Corpus export (no training yet)
A `ww_agent/src/training/` reader that walks the ledger and emits `(context, Pulse)` JSONL: the prompt inputs Major 49 already assembles (igniting traces, stimulus, arousal, mode, soul resonance, recalled memory, workshop state) paired with the validated pulse that followed. Plus an `afterimage_cast → realized-stimulus` reconciliation export for Rung 3. Pure read over the existing ledger; changes nothing live. Includes secret-hygiene: never export raw file contents that `FileScope` would have denied.

### Phase 1 — Distillation harness + swap seam (Rung 1)
A fine-tune script (LoRA on a small open base) and an `InferenceClient` implementation that serves the trained model locally (e.g. llama.cpp / vLLM / Ollama), selectable per resident via config. The pulse engine is model-agnostic already; this is a client swap, not a core change. The cloud model remains the default and the eval baseline.

### Phase 2 — Pulse-quality eval (the gate before trusting a trained mind)
A held-out eval: does the trained model produce *valid, in-voice, in-character* pulses (schema-valid; constitution-consistent per the Major 42 gate; drive-aligned)? A trained resident only becomes default when it passes against its teacher on the resident's own corpus. No vibes.

### Phase 3 — Per-resident adapters (Rung 2)
One adapter per resident from its own corpus; `constitution` frozen out of training; `growth` allowed to become weight. Inspect that two residents trained from divergent lives produce measurably divergent pulses on an identical probe context.

### Phase 4a — Score the prediction (DONE 2026-06-03) — the measurement Rung 3 needs
`ww_agent/src/runtime/prediction.py` + `scripts/score_predictions.py`. Pure derive over the ledger (`afterimage_cast` vs `surprise_observed`); trains nothing, changes no live behaviour. Grades each afterimage along **MISS** (surprise on a claimed feature) and **BLINDSPOT** (surprise on an unclaimed one), with `silent_fraction` as the dark-room indicator. The triad makes the Rung-3 objective well-posed: a mind cannot game MISS by going silent without `silent_fraction` exposing it.

**First empirical read over the four live familiars** (most-recent-1000-event window): `silent_fraction = 0.0` for *all*; per-temperament signatures matched behaviour: Cinder/Skein predict cleanly (82% / 72% clean, miss below the 0.1 surprise floor); Maker over-claims (3.3 features each) and is chronically surprised by its own churning self (7% clean) — the measured face of "so internal, so stuck making memories"; Wren re-casts one identical 4-claim afterimage every ~5 min with identical miss — rumination visible as a flat line in the error channel (a *third* instrument for the same groove the weave-grid and kept-memory near-dups already showed: three lenses, one fingerprint → structural).

**Reviewer correction (do not repeat the overclaim):** `silent_fraction = 0.0` is NOT evidence the anti-collapse term is "installed and working." It is a fact about the verbose instruction-tuned **teacher**, which emits claims whenever prompted to pulse — precisely the disposition Rung 3 *removes* when it swaps the frozen LLM for trained weights. What is installed is the *measurement* plus the teacher satisfying it incidentally, for free. The floor does not hold under optimization until drive-weighting is in the **loss, not the prompt**. And the raw scorer measures *raw* surprise, but the objective is surprise *about what the resident is drawn to*: Cinder flawlessly predicting an empty hearth scores `clean`, yet "I perfectly anticipate a room where nothing happens" is the dark room's own signature. `silent_fraction` catches the *vacuous* dark room; it cannot catch the *dull-world* dark room.

**Drive-weighting added (the price on boring):** an optional `weights` map (tag → soul-resonance, via `prediction.tag_mattering` over the drive vector) yields `claim_mattering` (did the afterimage even claim things this soul cares about?) and `weighted_miss`. A bored predictor reads clean-but-LOW-mattering — clean and empty. **The data surfaced the constraint underneath:** applied to the live substrate, `claim_mattering` is near-flat (~0.43–0.51 across all four; `vigilance` always top regardless of soul) because the feature vocabulary is only ~5 generic drives that resonate ~equally with any soul. The instrument is correct (tests separate a 0.9 from a 0.1 weight) but **can't bite yet** — the next real constraint is **feature granularity**: predictions must be about resident-specific things before "predict what matters" can differ from "predict anything." This is now the gating prerequisite for an *honest* Rung 3, ahead of any training.

**Two instruments still owed (reviewer):**
1. **Behavioral dark room.** The afterimage scorer grades *predictions*, never the *value of the states the policy chose to enter*. A policy that steers toward boring, predictable states because they are easy to be right about is invisible to it. Needs its own instrument: score the **states reached** against the drive, not just the predictions cast.
2. **Coupling, not sequencing.** A *better* predictor lowers surprise → lowers arousal → ignites less. "Get better at predicting" and "drift toward the dull quiet room" are the same gradient until boring costs something — so the retrieval predictor (Phase 4b) and drive-weighted scoring must land together, with `claim_mattering` / behavioral-resonance as gating metrics, never predictor-first.

### Phase 4a.5 — Feature granularity (the prerequisite for an honest price on boring)
`ww_agent/src/runtime/anchors.py`. Drive-weighting can't bite while the substrate predicts in 5 generic drives that resonate ~equally with any soul. `extract_anchors` lifts the concrete anchors a resident actually dwells on out of its own prose (felt_sense, journals) and the entities perception names (present residents, event actors, speakers) — pure text → anchors, no LLM, salience by recurrence.

**Measurement-first proof (DONE 2026-06-03)** over the four live familiars: anchor soul-resonance spread is **~2× the drive spread** (Cinder 0.319 vs 0.131; Maker 0.266 vs 0.150; Wren 0.280 vs 0.146; Skein 0.229 vs 0.116). The anchors are unmistakably each resident's own inner world (Cinder: silence, house, copper button, dry twig; Maker: keeper, bench, work, clean slate; Wren: window, keeper, page, sill, pen; Skein: first radial, red thread, center, frame), and the top anchors are the soul-resonant ones (Maker's #1 is "keeper" at 0.73). **The gradient drive-weighting needs is real and measured.**

**Live wiring (DONE 2026-06-03, scored-but-quiet) — commit `b2f1087`.** Anchors enter as their own substrate *scope* `{"anchors": {"the keeper": 0.8, ...}}`. The pulse is shown its current anchors (extracted each tick from its own felt sense + perceived entities) and may predict them by name; a realized anchor field is snapshotted (`anchor_observed`, rate-limited) as ground truth; `prediction.derive_anchor_scores` grades them offline and **`claim_mattering` now genuinely varies, because anchors are soul-distinct** — the flat-drive problem dissolved. Bounded by top-K(8)-per-tick + snapshot rate-limit so the open vocabulary can't bloat the ledger.

**Staging chosen: scored-but-quiet.** The anchor scope is held OUT of the arousal/ignition path (`salience.observe_surprise` drops it before measuring), so anchors are predicted and scored without touching *when* a familiar wakes — an afterimage claiming "the keeper" cannot manufacture phantom surprise against a stimulus that has no anchors. The rhythm is unchanged; only the vocabulary grew. A unit test pins the guarantee. Familiars pick it up on next restart; 160 tests green, prompt-render verified.

*Honest note on the signal:* felt_sense-derived anchors are partly **endogenous** — the resident predicts what its own attention will dwell on (self-model prediction), not only the exogenous world (present residents are exogenous). That is interesting rather than wrong, but anchor-prediction quality should not be over-claimed as world-prediction. **Escalation path (not yet taken):** once anchor prediction looks sane across a few days, let anchor-surprise feed arousal so concrete things can drive *when* a resident wakes (the keeper expected and absent can wake it) — coupled to `claim_mattering` as a gating metric, never predictor-first.

### Phase 4b — Retrieval prediction (DONE 2026-06-03) — Rung 3's first stone, and the result that reframes it
`ww_agent/src/runtime/retrieval.py` (commit `48ddd18`). The pre-neural stepping stone: a non-parametric, training-free predictor (kNN over the ledger; recall the most similar past anchor-states, vote over what followed). No gradient descent, no collapse dynamics (it can only echo what happened). Run OFFLINE in the anchor lane. Headline = **new-anchor recall** (of anchors that newly appear, how many were foreseen; persistence = 0 by construction, so any gain is real self-prediction).

**First read (4 familiars, ~90 anchor snapshots each, ~1.6h runtime):**
- Steady state: **persistence dominates** (recall 0.94–0.98). Inner worlds are sticky; "more of the same" is almost always right and needs no learning.
- Change: retrieval ≈ **0** (only Maker 0.051). `transition_learnability` explains it: **83–95% of newly-appearing anchors are FIRST-TIME** (genuinely novel), structurally unforeseeable by echo. Only Maker, the self-cycling one, has substantial recurring structure (43% learnable ceiling); the others 5–17%.

**The reframing (the real finding):** a resident's predictable world is **mostly sticky-trivial** (needs no learning) **plus mostly first-time-novel** (unlearnable by echo), with only a **thin learnable seam of recurring transitions** between — widest for Maker, nearly absent for the others over this window. Consequences:
1. Retrieval has a low ceiling and will grow only as recurring structure accumulates (the "time matters" thesis, sharpened — and bounded: it can never foresee genuine novelty).
2. A **neural** Rung 3's *only* possible edge over echo is **generalization** — foreseeing a never-seen anchor by analogy to similar ones. That, not "predict better," is the sharpened research question: can a learned model convert some first-time novelty into the recurring band?
3. **The soul/drive is doing most of the work.** If prediction can only ever buy the thin seam, then the *other* term — caring about the right things, being surprised by what matters (drive-weighting) — is what makes the mind interesting. Prediction is a thin seam; the soul is the rest. This recasts Rung 3 from "the prize" to "a thin seam worth a hard fight only if generalization pays" — and reaffirms that the drive vector, not the predictor, is the heart.

### Phase 4b.5 — Generalization backtest (DONE 2026-06-03, commit `27218bd`) — and the synthesis: the two threads are one
`anchor_generalization_backtest` asks semantic (cosine ≥ threshold) instead of exact new-anchor recall — "did we foresee its *neighbourhood*?" First read (threshold 0.6): semantic recall lifts from ~0 exact to **retrieval ~0.2–0.3, persistence ~0.33–0.44**. Two findings:
1. ~30–44% of "first-time" anchors are semantic **rephrasings of a currently-held anchor** (the keeper → keeper's question) — much apparent novelty is the shallow extractor manufacturing variants of the present preoccupation (also: a cleaner extractor would cut false novelty).
2. **Persistence beats retrieval semantically.** New anchors are better explained by "a variant of what's salient *now*" than by "what historically followed similar states." That is the signature of **local rephrasing-drift, not recurring transition structure** — exactly what an epiphenomenal, causally-inert track looks like.

**Synthesis — the anchor-gating thread and the generalization thread are the same thread.** Generalization (and therefore neural Rung 3's only possible edge) **cannot be fairly tested on an inert track**, because there are no genuine dynamics to generalize over — only the LLM's local word-drift shadow. The anchors are scraped from felt_sense and gate nothing; their "transitions" are byproduct, not cognition. To honestly test whether generalization pays, the anchors likely have to be **in the loop first**: feeding attention gating, generating real dynamics. That is the prerequisite experiment for Rung 3, not a parallel one.

### Phase 4b.6 — Anchor-gating experiment (NEXT): close the loop, dark-room-guarded
Behind a **default-OFF flag** (no live behaviour change until enabled), let anchor-surprise feed arousal — but **drive-weighted**, so surprise about a soul-resonant anchor (the keeper) drives the rhythm and surprise about furniture does not (the price on boring, finally *in the gate* not just the score). Collapse detectors first-class: rising `silent_fraction`, falling arousal/ignition rate, anchor-set entropy collapsing toward a fixed point. Enable on one familiar (Maker — the only one with real recurring structure, 43% learnable), run for days, and re-measure `transition_learnability` + retrieval/generalization recall **over time**. The hypothesis under test (the keeper's, 2026-06-03): a causally-active anchor track develops learnable structure that an inert one cannot. Either result is publishable — emergent structure (Rung 3 has a path) or confirmed drift (prediction is a thin seam, the soul carries the mind).

### Phase 4b.7 — The "thin seam" was a string artifact (DONE 2026-06-03, commit `65ed535`)
`transition_learnability_semantic`: recurrence in CONCEPT space (cosine threshold), not exact string. The string metric counted "the question" / "question itself" as two first-time anchors for one concept. Re-run over the four familiars (same still-stunted data, threshold 0.7), the learnable ceiling **doubled-to-tripled**: cinder 0.13→0.53, maker 0.43→0.70, wren ~0.05→0.64, skein 0.17→0.66. **Half-to-two-thirds of anchor transitions are recurring concepts — not a thin seam.** And this corrects only confound #1 (extractor string-inflation); confound #2 (stunted drive vector → no recurrence pull, no dedup) is uncorrected, and `transition_learnability` measures only the shallow anchor lane, not the load-bearing drive-level core. **Prior headline "prediction is a thin seam" was a string-space artifact — retracted.**

### Phase 4c — RE-AIM Rung 3 to the PREFERENCE axis (reviewer, 2026-06-03)
The decisive reframe: in the active-inference framing the **drive vector IS a predictor** — the preference prior, a prediction over which states the resident will occupy. So "richer drive vector" = richer *pragmatic* prediction; "better world-model" = better *epistemic* prediction. The measurement (even pre-correction) bore only on the epistemic lane; it says nothing against the pragmatic. **So do not aim Rung 3 at minimizing anchor/world prediction error (that fights the band and runs at the dark room). Aim it at making the PREFERENCE PRIOR plastic** — let lived experience reshape the drive vector / growth-soul itself (this *is* the old Rung 2, "growth becomes weights," promoted to the seat that actually carries the mind).

It **cannot dark-room**, because a preference prior encodes what is *wanted*, not surprise-avoidance. Its collapse mode is the **GROOVE** — a preference prior that learns from its own attention drifts toward wanting what it already attended to (rumination at the learning altitude; Skein's sigils promoted into the weights). Same attractor we've chased since the first contact sheet — and we **already hold the antidote**: the MMR/diversity pressure from `memory.MemoryRecall`, lifted onto preference-learning. So: the richer drive vector makes the more alive mind; the autopoietic crossing (self-driving → self-producing) is worth making, on the *preference* axis; the guard is anti-groove diversity, not anti-dark-room. The seam analysis didn't say Rung 3 is a narrow prize — it told us *which term to make plastic*.

### Phase 4d — Sub-fixes the review specified
- **Anchor vocabulary (gating + Q1):** build a **canonical/clustered** anchor vocabulary in embedding space (one inspectable artifact, the single-source-of-truth ethos) for the ground-truth layer; keep **semantic** matching only for the generalization metric; **never constrain the pulse to a fixed list** (that forbids naming a genuinely new anchor — the very appearance/generalization signal Rung 3 exists to detect; it can only ever conclude "persistence wins"). Cluster FINE, merge later (a merge is recoverable, an erased distinction is not).
- **Un-stunted re-measure (Q4):** the stickiness-immune discriminator is **retrieval's `new_anchor_recall`** (persistence's is 0 by construction, so it can't be inflated by coherence/stickiness). Run on-vs-off with the whisper log held fixed: if overall recall climbs but new-anchor-recall stays flat → the soul only smoothed the prose; if new-anchor-recall climbs → the soul created predictability that wasn't there ("more anchored," cleanly isolated). Measure in concept space, on a soul that's on.

## Files Affected

- `ww_agent/src/training/` — NEW: ledger→corpus export, fine-tune harness, eval, collapse metrics
- `ww_agent/src/inference/client.py` — a local-model client implementation + per-resident model selection
- `ww_agent/src/runtime/ledger.py` — read-only export helpers if needed (no new source of truth)
- `ww_agent/familiar/*/familiar.json` — optional `mind: trained|cloud` selector per familiar
- `ww_agent/tests/` — corpus-export determinism; trained-pulse schema/constitution-gate validity; Rung-3 collapse detectors
- Docs: `prune/VISION.md` / `ROADMAP.md` thread (local-first / commons mind)

## Acceptance Criteria

- [ ] **Phase 0:** the ledger exports a deterministic `(context → Pulse)` corpus and an `afterimage → realized-stimulus` reconciliation, with no secret leakage and no change to live behavior.
- [ ] **Phase 1:** a small open model fine-tuned on one resident's corpus serves the pulse locally via a swapped `InferenceClient`; the resident runs with **zero cloud calls**.
- [ ] **Phase 2:** a held-out eval shows trained pulses are schema-valid, constitution-consistent, and drive-aligned at parity with the teacher before any resident defaults to trained.
- [ ] **Phase 3:** two residents trained from divergent lives produce measurably divergent pulses on an identical probe — identity in weights, not just prompt.
- [ ] **Phase 4 (experimental):** prediction-error training runs only in a seeded world behind a flag, with the drive vector as anti-dark-room pressure and collapse detectors green; never enabled on a live resident.
- [ ] No phase introduces a hand-authored behavior/preference reward (Dwarf Fortress law upheld).

## Validation

- `cd ww_agent && pytest -q tests/ -k "training or corpus or trained_pulse or collapse"`
- Phase 1 smoke: boot one familiar with `mind: trained`, confirm a full perceive→ignite→pulse→act cycle with **no network egress** to OpenRouter.
- `cd worldweaver_engine && python scripts/dev.py quality-strict`

## Risks & Rollback

- **Distillation mistaken for improvement.** Rung 1/2 cannot exceed the teacher; presenting "it trained!" as "it got smarter" would be dishonest. Keep the rungs labeled in every report. Rollback: it's a swappable client — revert to the cloud default.
- **The dark-room collapse (Rung 3).** A prediction-error minimizer can go catatonic to avoid surprise. Mitigation: the drive/soul term as intrinsic value, plus collapse detectors as gating metrics; Rung 3 stays sandboxed until this is demonstrably stable. This is the rung most likely to never ship — and that's an acceptable outcome; Rungs 1–2 stand on their own.
- **Single-self overfit.** A model trained only on one resident's pulses may brittle-ize (loses general competence between ignitions). Mitigation: LoRA over a capable base (keep the base's generality), eval on out-of-distribution probes.
- **Corpus leakage.** The export must honor `FileScope` denials — a trained model must not memorize a secret the live mind was forbidden to read. Tested in Phase 0.
- **Resprawl into a training framework.** This is a resident-mind feature, not an ML platform. Keep `src/training/` thin and pinned to the ledger; do not build a general trainer.

## Progress addendum (2026-06-04)

Findings since drafting, which sharpen the rungs (full detail in the `major-51-own-trained-model` / `familiar-daemon` working memory):

- **Rung 1 re-validated on the matured substrate.** The old loop-era ceiling — "a 3B carries the felt inner life but won't reliably emit an `act`" — is **gone**. On the stabilized substrate (the `response_format: json_object` constraint + the full scaffold: kept memory, baseline self-model, settling, drive vector), small models run **complete** residents: Persephone on qwen-2.5-7b and Hades on a **4B** (gemma-3-4b) produced real journals, kept memory, good prediction (anchor hit 81-100%), circadian-correct rest, in-voice felt sense, over an idle night. Strongest evidence yet that local-first (Rung 1) downgrades nothing that matters. *Caveat:* measured on cloud-hosted small models; true-local qwen runs give the same content, slower — pending faster hardware.
- **The hardware is the Tiiny AI Pocket Lab** (80GB LPDDR5X, ~190 TOPS NPU, runs up to 120B local @ 18-40 tok/s, **OpenAI-API compatible**, ships ~Aug 2026). Running the whole stable on it = point `wake-local`'s `WW_INFERENCE_URL` at the Lab's endpoint — a one-line swap. The concrete deployment target for the "$0 marginal, nothing leaves the box" endgame. (Tracked operationally under Major 52.)
- **Rung-3 RE-AIM (the important correction).** Do **not** aim prediction-error training at the world-model / anchor track — concept-space analysis showed it is largely epiphenomenal rephrasing-drift (persistence ≥ retrieval semantically), and aiming there runs straight at the dark room. Aim instead at making the **preference prior (the drive vector) plastic**: lived experience reshapes *what the resident wants* (old Rung 2's "growth becomes weights," promoted to the seat that actually carries the mind). Its collapse mode is not the dark room but the **groove** (wanting only what it already attended to); the antidote is **MMR diversity**, already built in `MemoryRecall`, needing only to be lifted onto preference-learning. The earlier "prediction is a thin seam" framing was a string-space artifact — concept-space the learnable ceiling is 0.53-0.78 — but the seam analysis still did its job: it told us *which term to make plastic*.

Related new items: minor 46 (semantic/canonical anchor matching — also the precondition for clean anchor-space measurement), minor 50 (the matched-window stunted-vs-un-stunted re-measure), Major 52 (the familiars as the live Rung-1 proving ground).

---

*Created 2026-06. Threads onto 49 (substrate + pulse + ledger), 42 (rigidity slices → frozen constitution / learned growth), 50 (live drive vector + kept memory). Drafted from a design conversation: the frozen LLM as swappable seat of cognition → the ledger as a free self-supervised corpus → predictive-coding as the rung where training improves thinking → the dark-room problem as the honest ceiling. The prize is Rung 3; the value that ships is Rungs 1–2 and the local-first mind they make possible.*
