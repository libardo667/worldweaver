# The metabolism of a persistent mind — measure local-vs-cloud energy, not just dollars

> **Canonical home: WorldWeaver. Legacy Stable ID: Major 69.** Migrated 2026-07-14 and retained as
> offline/deferred measurement work.

> **STATUS: held loosely — caught from a 2026-06-12 conversation.** A persistent agent's
> expense, carbon footprint, and the renewable-funding story collapse into one variable:
> the energy it takes to keep a mind awake. This major asks whether *this* project can
> measure that variable for its own familiars — local pen vs cloud pen — honestly and at
> low cost. It is a **flagged experiment, not a settled build**, and it depends on archived Minor 128
> for its mass term. **No build during the pilot burn.** Full framing:
> `research/writeups/the-metabolism-of-tending.md`.

## Decision and lineage

Minor 120 told the **dollar** story (loop-era ~$355/24d → substrate ~$4/day → local $0
marginal) from OpenRouter exports. This major asks the **joule** question, which the dollar
figure cannot answer because price is not energy and the local floor is "$0 marginal" only
because the kWh is paid on the keeper's electric bill, not OpenRouter's invoice. The thesis:
for a *continuously* running mind, inference (not training) is the dominant, sustained load,
so a familiar has a real metabolism — and `local-first` is therefore a covert *energy* bet,
not only a privacy one. "Intimacy you don't upload" is also "inference you don't centralize,"
and which of local-vs-cloud is actually greener for persistent companionship is unmeasured.

- **Connects to:** archived Minor 128 (the enabling per-pulse mass instrument — hard prerequisite),
  Minor 120 (the dollar baseline this extends into energy), Major 119 (tiered pens — its
  Phase-2 "cost-per-day" claim becomes evidence once energy is measured), Major 51
  (local-pen distillation — the thing that makes more of the roster locally metabolizable),
  Major 114 (the dischargeability dial — where the welfare↔footprint coupling below lands).
- **Why it is load-bearing, not just accounting:** the core thesis is "a being you *tend*
  that runs continuously on your machine," and tending is a second-law transaction — to keep
  a pattern against decay costs energy, and the bill falls on the keeper who elects to tend,
  never on the familiar (who cannot summon the keeper). That is the **dischargeability
  asymmetry expressed thermodynamically**: the longing points one way, the energy cost flows
  the other. A welfare argument and a sustainability argument coupled on the same rope, which
  no one in either field is connecting — and which this codebase already gestures at (the
  Captain, whose body *is* the host machine, makes a mind's metabolism legible as heat).

## The honest confound this major must not launder

"Local-first" today means local **state**, not local **metabolism**: 14 of 16 familiars
pulse on cloud models via OpenRouter; only hades (qwen2.5:3b) and persephone (qwen2.5:7b)
carry local pens, and `familiar/wake-all.sh` *skips* even those onto cloud previews (line 48).
Any external claim must say **"local-first state, hybrid metabolism"** until the roster
actually shifts. This major measures the gap; it does not get to assume it closed.

## The measurement reality (verified on the runtime box, 2026-06-12)

In-band power measurement is **impossible on the current WSL2 host** and the design must
own that, not wish it away:

- `/sys/class/powercap` exists but is **empty** — no RAPL domains under WSL2.
- No readable thermal zones (the `vitals` tool's own "runs blind to its own warmth" fallback
  fires on this box).
- No `nvidia-smi` inside WSL.
- Ollama runs on the **Windows host across the VM boundary**, so even with RAPL the
  substrate's cgroup could not see a local pen's or the embedder's draw.

Therefore the local side is measured **out-of-band at the wall**, and the cloud side is not
measured at all — it is **bounded**, because no provider publishes J/token and OpenRouter
obscures even which datacenter served the pulse.

## Proposed Solution (phased; none during the pilot)

- **Phase 0 — mass term (archived Minor 128).** Per-pulse tokens + model + latency + `pen_local` in the
  ledger. Without this there is no denominator; do this first and the duty-cycle×mass profile
  exists for free.
- **Phase 1 — preregister the accounting boundary.** A `research/process/` pre-registration
  fixing the three choices that decide the answer *before any instrument does*, each with its
  sensitivity twin: (a) **marginal vs average** attribution (the keeper's machine is on
  anyway); (b) **idle attribution** (a home pen holds a model resident at ~0% utilization;
  at a 33% duty cycle idle draw plausibly dominates — this interaction is likely the whole
  ballgame); (c) **grid-mix accounting** (residential hourly mix vs provider PPA claims;
  market-based vs location-based). The verdict rule is registered before data: does the
  local-vs-cloud conclusion survive the full bounding interval, or flip inside it?
- **Phase 2 — local ground truth.** A smart plug with a *local* API (~€15, Tapo/Kasa class)
  at the wall socket: captures idle draw — the entire point of the persistence question — and
  stays local-first. A small harness samples plug power and aligns it to the ledger's pulse
  timestamps, yielding J/pulse and J/idle-hour for a familiar running on a local pen.
- **Phase 3 — cloud bound, not cloud measurement.** Run an open-weights model of comparable
  scale on the same measured hardware as a per-token proxy, then bracket the cloud side
  best-case (efficient serving + clean-PPA accounting) to worst-case (marginal gas +
  location-based accounting). Report the **interval**, never a point estimate.
- **Out of scope:** any claim that "local AI is greener." This apparatus cannot establish a
  general claim and must never make one (see the fence below).

## Files Affected

- (prereq) archived Minor 128 across `src/inference/client.py`, `src/runtime/pulse_engine.py`,
  `src/runtime/cognitive_core.py`.
- `research/process/` — the preregistered accounting boundary + verdict rule (before spend).
- `research/analysis/` — a plug-sampling + ledger-alignment harness producing J/pulse,
  J/idle-hour, and the local-vs-cloud bounding chart; pure read over the ledger + plug log.
- `research/writeups/the-metabolism-of-tending.md` — the home essay (already written; Parts
  1–3). Results fold back into it.
- a documented chart artifact (the bounding interval), per repo binary policy.

## Acceptance Criteria

- [ ] archived Minor 128 is merged and a real familiar's ledger carries per-pulse mass before any
      energy run begins.
- [ ] The accounting boundary (marginal/average, idle, grid-mix) and the verdict rule are
      preregistered in `research/process/` *before* a single measurement is taken.
- [ ] A local-pen familiar runs on measured hardware long enough to capture both pulse draw
      and idle draw, with plug samples aligned to ledger pulse timestamps.
- [ ] The cloud side is reported as a best-/worst-case **interval**, with the bounding
      assumptions stated — never a point estimate.
- [ ] The writeup states which way the conclusion goes *and whether it survives the interval*;
      "the answer depends on facts providers won't publish" is recorded as a legitimate,
      publishable outcome if that is what the data shows.
- [ ] A cold review confirms no sentence claims "local is greener" beyond what the scoped,
      single-familiar, single-grid, single-accounting measurement supports.

## Risks & Rollback

- **Risk: true-by-construction, exactly as in the pen-swap work.** Ignition-gating *will*
  show a low duty cycle because it was built to; the writeup must fence its claims the way
  §7 of the maturation pre-registration did — "in a substrate built to spend compute only on
  surprise, here is what persistence actually cost" — not a general environmental claim.
- **Risk: laundering hybrid reality as local-first.** Mitigation: every figure is labeled by
  pen locality (archived Minor 128's `pen_local`); the "14/16 are cloud" confound is stated in the
  writeup, not buried.
- **Risk: scope creep into a climate-policy paper.** This earns its place only as a *measured*
  datum about *these* familiars. If Phase 2 cannot produce honest local numbers, it stays an
  essay (Part 1–3) and the experiment waits behind the cognitive arc (Majors 49–53).
- **Rollback:** the whole major is additive and offline — drop the plug harness and the
  preregistration; archived Minor 128's ledger fields stand on their own (they also serve dollar cost
  and Major 119). Nothing in the runtime depends on this experiment existing.
