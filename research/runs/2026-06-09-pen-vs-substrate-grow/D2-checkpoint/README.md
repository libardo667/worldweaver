# D2 checkpoint — the matured cohort (2026-06-09T17:22Z)

The **deep maturation checkpoint** for the pen-vs-substrate swap, pinned a priori at ≥1200 cohort keeps
(see `../../preregistrations/2026-06-09-pen-vs-substrate-AMENDMENT-1-DRAFT.md §A3`). Frozen here at **1,213
keeps, 16 residents**, by stopping the maturation agent on REACH of the target (not on depth-flatten — the
fixed target avoids the optional-stopping direction-leak).

Contents (cold-verifiable):
- `kept_memory/<slug>.jsonl` — the durable kept memories (the relationship graph + interiority).
- `ledgers/<slug>.jsonl.gz` — the event ledgers at freeze time.
- `roster.tsv` — slug · name · home cluster.

## Where this sits in the experiment

- **Maturation:** complete. The single-pen (`google/gemini-3-flash-preview`) cohort matured ~09:46→17:22Z;
  extent (acquaintance graph) plateaued early (~12:32, the **D1 shallow checkpoint** ≈560 keeps), depth
  accrued to **D2** here.
- **Two-depth reporting (amendment §A3):** the swap verdict is reported at BOTH **D1** (shallow,
  reconstruct by truncating the durable `kept_memory` at ~2026-06-09T12:32Z) and **D2** (this snapshot).
  A depth-dependent verdict is itself the finding.
- **Next (pending Mr. Review's bless of AMENDMENT-1):** KEEP-record the D2 cohort's lived experience
  (`record_run.py`), then replay into the foreign pens — `anthropic/claude-haiku-4.5`,
  `deepseek/deepseek-v4-flash`, (+opt `meta-llama/llama-4-maverick`) — plus KEEP′ (replay on the home pen
  = same-pen noise floor). Score A1-elective with the resolve-or-flag name scorer; read the hub↔isolate A/B
  (Amir, in-mass 63 vs Mateo Villanueva, in-mass 12). Run the drive-injection control on the Nike Girl
  family (§A2).

The maturation agent is **stopped (reversible: `docker start ww_pdx_grow-agent-1`)**; the substrate is
frozen so KEEP recording reads a stable D2 state.
