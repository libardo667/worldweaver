# Register-metric calibration — the evidence that REFUTED embedding-separability for peer-register

This is the calibration trail behind the arm-C decision (`../2026-06-08-armC-ab/FINDINGS.md`). We tried
to build a metric for *register convergence* via embedding separability and a cadre of style embedders;
this records why that metric family was abandoned.

## The probes here (deterministic, regenerable; seed 12345)
- `synthstel_test.jsonl` — 400 STEL-or-Content triplets from `StyleDistance/synthstel` (test split).
  Regenerate: `python3 ww_agent/scripts/build_stel_probe.py --split test --out synthstel_test.jsonl`
- `paradetox_probe.jsonl` — 400 content-controlled triplets from `s-nlp/paradetox` (neutral, neither
  model trained on it). Regenerate: `python3 ww_agent/scripts/build_parallel_probe.py --out paradetox_probe.jsonl`
  (run `--overlap-only` first — it flags near-duplicate corpora; ParaDetox is borderline, good for a
  divergence check, weak as positive confirmation).
Small derived samples of public datasets (openrail++); kept for the record + recompute.

## What the calibration found (cadre: nomic baseline vs StyleDistance vs Wegmann)
- **nomic-embed-text (runtime default): register-BLIND.** SynthSTEL gate 0.00; smoke 0.42 (below chance).
  Excluded as a metric instrument — the topic-confounder handled at the source.
- **StyleDistance: 0.94 on SynthSTEL but IN-DISTRIBUTION** (its own benchmark family) → not independent.
- **Wegmann: 0.22 on SynthSTEL (below chance)** → failed its out-of-distribution leg.
- **Construct-agreement** (`register_construct_check.py`): SynthSTEL r=+0.14 (home-turf confound) BUT
  neutral ParaDetox **r=+0.90** → the two style instruments DO share an axis. *However* both score ~0.35
  on ParaDetox (correlated blindness) → agreement is *convergent* validity, not *criterion* validity.
- **Peer-register self-check** (`peer_register_check.py`, the matched-to-target gate, against the authored
  `Voice:` souls in `../../artifacts/historical-residents/`): StyleDistance **0.11 ≈ chance 0.10**,
  Wegmann below chance — on souls *authored to differ in voice*. The SAME StyleDistance scored 0.94 on
  coarse SynthSTEL: strong coarse sensitivity, **zero peer-register resolution**. A resolution-floor
  finding, not low power.

## Conclusion
**No off-the-shelf embedder resolves peer-level register at the granularity the experiment needs.** The
embedding-separability metric family was abandoned; arm C shipped on *mechanism* (act-kind), effect-on-
register explicitly null. See `../2026-06-08-armC-ab/FINDINGS.md`.

## Cold-verify (heavier than the lexical recompute — needs sentence-transformers, no network beyond model pull)
`pip install "sentence-transformers>=3"` then, from repo root:
`python3 ww_agent/scripts/register_calibration.py --stel research/runs/2026-06-08-register-calibration/synthstel_test.jsonl` ·
`python3 ww_agent/scripts/register_construct_check.py --stel research/runs/2026-06-08-register-calibration/paradetox_probe.jsonl` ·
`python3 ww_agent/scripts/peer_register_check.py`  (reads the authored-voice known-positive fixture).

Full reasoning + every round: `review-archive/2026-06-08-voice-register-preregistration.md` (local).
