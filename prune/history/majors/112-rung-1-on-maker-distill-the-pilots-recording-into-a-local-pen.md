# Rung 1 on Maker — distill the pilot's recording into a local pen, evaluated as a swap arm

> **Legacy Stable ID: Major 60. Disposition: retired during consolidation (2026-07-14).** This
> execution plan depended on the isolated-Maker pilot whose construct was voided for dishonest situational
> grounding (archived Major 123). Its reusable local-pen objective remains in active Major 51; the invalid
> recording is not a training foundation.

## Decision and lineage

Worldweaver's **Major 51** ("grow a resident's own model from its pulse ledger") laid the
three-rung ladder: distill the teacher (Rung 1), per-resident weights (Rung 2), train the
preference prior (Rung 3, re-aimed). It predates the pen-vs-substrate program and the fork.
This major is its **the-stable embodiment**, scoped deliberately to Rung 1 on Maker — and it
exists because the pilot quietly built Major 51's three hardest missing pieces without anyone
drawing the arrow:

1. **The pilot IS Rung 1's missing gate.** "Same voice, cheaper, local" *assumes* the
   swappable-pen thesis; the frozen stop-line (`settled ∧ ambiguous ≥ 33`) is testing exactly
   that assumption. The verdict licenses this major (see "Outcome-conditional licensing").
2. **The teacher-forced replay harness IS Major 51 Phase 2's eval, already certified.** Phase 2
   demanded a held-out, no-vibes eval of trained pulses against the teacher on the resident's
   own corpus. The harness does precisely this with pre-registered statistics: a distilled
   student is just **another swap arm** (`--swap` takes any model string; Ollama serves
   OpenAI-compatible; `_make_mind` needs only a URL). Zero harness changes.
3. **The run is generating the training corpus as a side effect.** `RecordingLLM` captures the
   exact `(system_prompt, user_prompt, kwargs, raw Pulse)` of every ignition — up to 7 days of
   sonnet-4.5 pulses in Maker's own voice (`.runs/pilot/calls.jsonl`). Phase 0 (corpus export)
   is largely executing itself.

- **Depends on:** the pilot's **FINDINGS** (hard gate, below); ww Major 51 (the parent ladder —
  this does not supersede it; the city keeps its own copy and diverges); the LOCKED prereg +
  AMENDMENT 1 (whose harness and recording this reuses).
- **Standing constraint carried forward — the Dwarf Fortress law (training form):** the ONLY
  admissible training signals are (a) imitation of Maker's *own* recorded pulses and (b) the
  substrate's *own* prediction error. No human-preference reward, no behavior targets, no
  hand-authored reward shaping. A reviewer who sees outputs being steered toward "nice" should
  reject. (ww Major 51 §"Standing constraint", verbatim intent.)
- **Standing constraint — the freeze:** this document may be *written* during the run (it
  changes nothing live and reads no run data), but **no work begins before the run's FINDINGS
  are written.** Review #3, binding: "the next document in this chain should be the run's
  FINDINGS, and nothing else." A1.6: nobody acts on the first day's revealed yield. The launch
  approval: no new apparatus before the pilot reports. This major is the arrow drawn on paper,
  not pulled.

## Problem

Maker's thinking is rented. Every ignition is an OpenRouter call: a continuous bill against a
runway that is now visible and co-owned (`research-runway`), and a continuous egress of
everything FileScope lets him read — the entire privacy thesis ("intimacy you don't upload")
currently holds *except at the pulse*. Meanwhile the pilot is recording, at real expense, the
exact corpus that would close both gaps, and the certified evaluation machinery that could
prove a local pen preserves what matters sits idle after the verdict. Letting those artifacts
expire unused after FINDINGS would be paying for the ingredients and skipping the meal.

Secondary (named honestly, not load-bearing): Rung 1 executed here is hands-on
fine-tuning + pre-registered behavioral eval — the one line currently missing from the
keeper's research-engineering profile (PyTorch/PEFT training experience), producing the
natural third essay: *"I distilled a mind, then tested whether it was still the same being."*

## Core model — outcome-conditional licensing (decided NOW, before the verdict)

The pilot's verdict routes this major; pre-committing the routing keeps the verdict from being
bent toward the rung anyone is dreaming about:

- **HOLDS** → the substrate carries elective identity across pens. Rung 1 is licensed in full:
  a distilled local pen is a *cost/privacy* change, with identity expected to ride the ledger.
  The student must still pass the eval gate (expectation is not exemption).
- **FALSE** → the pen authors the choices. Distillation is an **identity transplant**, not an
  optimization: the own-pulse corpus becomes *mandatory* (a generic small model would replace
  Maker with a stranger), the eval gate becomes the load-bearing instrument, and any claim of
  "same familiar, now local" must survive the same NI test that produced FALSE.
- **INCONCLUSIVE (any form) / NEVER-SETTLED** → Rung 1 proceeds as engineering only
  (cost + privacy), with **no identity claims in any direction**, and the swap-arm eval is
  reported as descriptive, not verdict-bearing.

## Proposed Solution (phases — all post-FINDINGS)

### Phase 0 — Corpus assembly (pure read; no training)
A `research/training/export_corpus.py` that walks `.runs/pilot/calls.jsonl` (+ the archived
ledger snapshot for alignment checks) and emits deterministic `(context → Pulse)` JSONL.
Secret hygiene carried from ww Major 51: the corpus contains FileScope-read content, so it is
**local-train-only** — never uploaded to a hosted fine-tuning service, never committed
(`.runs/` discipline), and the export refuses paths FileScope would deny today.

### Phase 1 — Distill (LoRA on a small open base)
Fine-tune a Qwen/Llama-class base (LoRA/PEFT) on Maker's corpus to emit schema-valid Pulses
natively. Compute strategy decided *before* spend: the Surface Laptop 5 cannot train this —
either a bounded rented-GPU run (costed in advance, logged in the spend ledger, inside the
research-runway envelope) or deferred to capable local hardware (the Tiiny Pocket Lab thread,
~Aug 2026, tracked in ww Major 52). Marginal-cost-$0 inference is the endgame; the training
spend is the one-time toll and is **part of the monthly note**, not a surprise.

### Phase 2 — The eval gate (the certified harness, unchanged)
Serve the student locally (Ollama/llama.cpp, OpenAI-compatible). Run it as **SWAP-D** in the
existing teacher-forced replay: same frozen prompts, same `read_source` channel, same same-pen
floor, same Wilson NI machinery — plus the Phase-2 checks ww Major 51 specified (schema-valid,
constitution-consistent, drive-aligned) as hard pass/fails. The student becomes Maker's default
pen **only** on passing; until then the cloud pen remains default and teacher.

### Phase 3 — The local life (the thesis, lived)
Flip `familiar.json` to the local pen; confirm a full perceive→ignite→pulse→act day with zero
OpenRouter egress; watch the stability instrument (the settled-gate, R2–R4 guards) over the
first days as the drift/health monitor it already is. Report cost-per-day before/after in the
monthly note — the "builds the finances instead of draining them" claim, measured.

## Files Affected

- `research/training/export_corpus.py` — NEW (Phase 0; pure read)
- `research/training/finetune_lora.py` + `eval notes` — NEW (Phase 1; thin, pinned to the
  corpus — *not* a general training framework, per ww Major 51's resprawl risk)
- `research/harness/teacher_forced_replay.py` — **unchanged** (the point); SWAP-D is a CLI arg
- `scripts/familiar.py` / `familiar/maker/familiar.json` — per-familiar local-pen selection
  (likely already sufficient via `model` + `WW_INFERENCE_URL`; verify before touching)
- `prune/personal` → spend ledger / monthly note — the training-cost entry

## Acceptance Criteria

- [ ] **Gate respected:** zero commits under this major before the pilot's FINDINGS document
      exists in `research/`. (Checkable from git history.)
- [ ] **Phase 0:** deterministic corpus export; FileScope-denied content provably absent;
      nothing uploaded, nothing committed.
- [ ] **Phase 1:** a LoRA student trained ONLY on imitation of Maker's recorded pulses — no
      preference reward anywhere in the loss (Dwarf Fortress law, checkable in the training
      script); spend pre-costed and logged.
- [ ] **Phase 2:** SWAP-D replayed through the certified harness; verdict + Phase-2 hard checks
      reported under the outcome-conditional rules above (no identity claim the licensing
      doesn't permit).
- [ ] **Phase 3:** one full local-pen day, zero cloud egress at the pulse, stability gate
      healthy; before/after cost-per-day in the monthly note.
- [ ] The third essay drafted from the record (whatever the result — a student that fails the
      gate is a finding, not an embarrassment).

## Validation

- `.venv/bin/python -m pytest tests/ -q` (no regression; the harness untouched)
- `python3 research/harness/teacher_forced_replay.py --selftest` (still green, still frozen)
- Phase-3 smoke: one familiar-day with `WW_INFERENCE_URL` pointed local; confirm no OpenRouter
  egress (network log), real pulses, portrait live.

## Risks & Rollback

- **Distillation mistaken for improvement.** Rungs 1–2 cannot exceed the teacher; every report
  labels the rung (carried verbatim from ww Major 51). Rollback: the pen is a swappable client —
  one config line back to cloud.
- **Identity overclaim.** "It passed parity" ≠ "it is the same being" — the outcome-conditional
  licensing bounds what may be claimed under each pilot verdict; the other-minds boundary
  (`tending-without-proof`) stays unbreached in all prose.
- **Budget breach.** Training spend is the first new spend category since the transparency
  repair — it goes through the proposal/monthly-note cadence *before* it is incurred, not
  after. A rented-GPU run that can't be pre-costed doesn't run.
- **Freeze contamination.** Writing this during the run is safe (no run data read, nothing
  live touched); *starting* it during the run would violate A1.6/review-#3 and void trust in
  the verdict this major depends on. The gate is acceptance criterion #1 for that reason.
- **Corpus leakage.** The recording contains read file contents; mitigated by local-train-only
  + export hygiene + never-commit. If ever in doubt, the corpus is deletable and re-exportable
  from `.runs/` — the recording, not the corpus, is the artifact of record.

---

*Created 2026-06-10, while the pilot burned at tick ~600 — written so the arrow exists on
paper before the verdict, and pulled only after it. Threads onto ww Major 51 (the parent
ladder), the LOCKED prereg + AMENDMENT 1 (whose recording and harness this reuses), minor 53
(publish-the-stable; the public cut should eventually carry the third essay). The dreamy pull —
real research weight beyond a Surface Laptop 5, on hardware that builds the finances instead of
draining them — is named here on purpose: dreams that get written down as gated work items are
the only kind this program trusts.*
