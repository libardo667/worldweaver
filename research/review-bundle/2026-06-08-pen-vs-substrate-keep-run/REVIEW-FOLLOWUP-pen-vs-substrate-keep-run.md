# Mr. Review — progress report + cross-check BEFORE the powered divergence run

We built the perception-replay harness you steered us to (v3), ran the KEEP recording, and **proved the
harness faithful** — but the curation surface came back **starved**, and we're deliberately NOT starting
the multi-arm divergence burn without your cross-check. This round is a checkpoint, not a result.

Everything here is cold-verifiable: harness code in `ww_agent/scripts/pen_swap/` (with `DESIGN.md`), run
evidence in `research/runs/2026-06-09-pen-swap-keep/` (`FINDINGS.md` + gzipped recordings + kept-memory),
the v3 pre-registration at `research/review-bundle/2026-06-08-pen-vs-substrate-v2/`. `STANDING-BRIEF.md`
is included here.

## What we built (and what's proven)
- **Perception-replay at the world-client HTTP choke points** — record a cohort's exact lived experience
  (KEEP), replay the byte-identical perception into fresh copies on a different pen. On replay the real
  `perceive()` runs unchanged (substrate side-effects preserved); only the pen varies. Zero production-path
  change (CognitiveCore just gets a different client). Offline record→replay unit-tested.
- **Reproducible cohort:** 15-soul armC cast rehydrated from PUBLIC data (souls now published + arcon
  ledgers); kept-memory provenance verified pure-arcon.
- **PARITY — the gate you demanded — PASSES CLEAN:** a same-pen replay drains the recording with **0
  misses / 0 leftover reads per resident** (every world read served from the recording, in order, fully
  consumed). Recompute: `replay_run.py --arm-dir <pristine> --keep-dir <recordings> --rounds 30`.
  - *Transparency:* the first cut had 1 miss + 2 leftover/resident — a boot handshake difference (replay
    reused KEEP's session id → validated it via an extra `get_scene` → scene queue off-by-one). Fixed
    (fresh-bootstrap + session-id normalization); now 0/0.

## The problem we want your eyes on BEFORE spending
**The curation surface is starved.** KEEP (15 residents × 30 rounds, claude-haiku) produced **6 new
durable keeps cohort-wide — only 5/15 residents kept anything — ~1.3%/tick.** Keeps are deliberate by
design, but at this rate the memory-curation divergence measure is **unpowered**: the per-resident paired
read (same resident, same experience, different pen) is impossible at ~0–2 keeps/resident, and even a
pooled read is ~6 vs ~6. ~10 keeps/resident would need ~750 ticks/resident — infeasible at this rate. No
divergence number has been computed; we will not ride a verdict on 6 keeps.

## What we're asking (cross-check + pre-mortem)
1. **Parity sufficiency.** Does 0/0 read-drainage satisfy your faithfulness gate, or do you want the
   *deterministic substrate trajectory* (per-tick arousal / surprise / recalled-set) compared
   tick-for-tick between KEEP and a same-pen replay, not just the read stream?
2. **The starved surface — the load-bearing question.** Is `memory_kept` simply the wrong divergence
   surface at feasible scale? Candidate directions, none yet chosen: (a) a much longer / curation-dense
   run; (b) switch to **relationship/edge-formation** (replies, who-addresses-whom — far more frequent
   than keeps — but this cohort is relationship-sparse: 5 private directed carries); (c) redefine the
   curated-self surface entirely; (d) read divergence on the *content of the keeps that do fire* plus a
   denser secondary. What would you measure, and what's the minimum keep/edge volume you'd accept?
3. **KEEP pen choice for the powered run.** We ran claude-haiku (the cohort's configured pen); it's slow.
   We're considering **gemini-3-flash-preview** for a powered re-run: faster live recording, it's the
   project's default runtime pen (most representative), and gemini-vs-claude is the *known surface-
   divergent pair* (so the positive control will clearly fire). Does the KEEP-pen choice bias anything?
   Caveat we see: keep/curation RATE may itself be pen-dependent — we don't want to pick a pen that
   merely inflates the surface.
4. **Design drift.** Did the implementation drift from the v3 you greenlit (perception-replay,
   KEEP/KEEP'/SWAP×2 with KEEP' as noise floor, the positive control DISCOVERING pen-difference rather
   than assuming it)?
5. **The counterfactual, restated now it's real.** Replay feeds SWAP residents KEEP's recorded perception
   — i.e. a SWAP-pen mind reacting to a KEEP-pen world ("dreaming through KEEP's day"). Constant across
   all replay arms, so it cancels in the SWAP-vs-KEEP' contrast. Still the right counterfactual for "is
   the durable self pen-robust"?
6. **Pre-mortem the powered run.** Predict the divergence outcome; name the confound we'll hit.

The deal stands: if you predict an outcome and we build the powered run to be able to falsify you, that's
the cross-check working before we burn.
