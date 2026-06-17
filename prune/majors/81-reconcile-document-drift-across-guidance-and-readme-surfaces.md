# Reconcile document drift across guidance and README surfaces

## Decision and lineage

This is a fast-moving project whose architecture was rebuilt (the loop bank → salience substrate +
predictive pulse, Major 49) and whose paths were renamed (`improvements/` → `prune/`). The **code** moved;
much of the **prose** did not. The result is a layer of guidance/README docs that describe a superseded
architecture and **actively misdirect both the keeper and other agents working in this workspace**.

- **Status:** proposed (recon done 2026-06-16, during the public-repo cleanup pass). Captured now; the
  rewrite is deferred to its own execution.
- **Source of truth:** the root `CLAUDE.md` (current, self-aware) plus the live code under
  `ww_agent/src/runtime/` and `worldweaver_engine/src/`. Every doc surface should agree with these or be
  explicitly labeled historical.

## Problem

A 2026-06-16 reconnaissance over the 269 tracked `.md` files found the drift concentrated in the
human/agent-facing guidance and per-module READMEs (not the research evidence or the dated work-item
ledger). The worst offenders:

- **`ww_agent/AGENTS.md`** — its "read these first" list names `src/loops/README.md` as *"the cognitive
  architecture (most important file)."* That doc is **self-labeled SUPERSEDED**. Every fresh agent is
  pointed at the wrong architecture first. Highest-impact single fix.
- **`ww_agent/src/README.md`** — the module map documents **removed** files: `loops/{base,fast,slow,mail}.py`,
  `memory/{working,provisional,retrieval}.py`, `identity/loader.py` loading `tuning.json`. The real runtime is
  `src/runtime/` (substrate + pulse). The map is flatly wrong.
- **`ww_agent/README.md` + per-module READMEs** — `src/{identity,inference,memory,world}/README.md`,
  `config/README.md`, `scripts/README.md`, `tests/README.md`. Each describes loop-era behavior; audit vs the
  current code and update, label historical, or remove.
- **`ww_agent/src/loops/README.md`** — already self-labels SUPERSEDED (good). Keep as history; the fix is to
  stop other docs pointing at it as current.
- **`worldweaver_engine/{README.md, FEDERATION.md}`** and the **`worldweaver_engine/CLAUDE.md` shim** — carry
  stale `improvements/` path references and loop-era architecture language.
- **`prune/v6_docs/`** (7 files incl. `V6_MANIFESTO.md`, `06-guild-ranks-advancement-and-embodiment.md`,
  `07-social-feedback-and-adaptation.md`) — a superseded "V6 mixed-intelligence **guild** platform" vision set.
  Guild is retired (Major 68); this set contradicts the current `prune/VISION.md`.
- **Root `README.md`, `CLAUDE.md`** — spot-verify current (root `CLAUDE.md` is largely accurate and
  self-aware; treat as the reference).

## Proposed Solution

Bring every guidance/README surface into one of three honest states: **accurate-and-current**,
**explicitly-historical** (banner like the loops README already carries), or **removed**.

1. Fix `ww_agent/AGENTS.md` first — repoint the reading order at the substrate (`src/runtime/`,
   `cognitive_core.py`, the root `CLAUDE.md` description); demote the loops README to "historical."
2. Rewrite `ww_agent/src/README.md`'s module map to the real `src/runtime/` + `src/familiar/` layout.
3. Audit each per-module README against its module's current code; update, banner, or delete.
4. Update `worldweaver_engine/{README.md, FEDERATION.md}` and the `CLAUDE.md` shim (`improvements/` → `prune/`;
   current architecture).
5. Resolve `prune/v6_docs/`: archive it or add a clear "superseded by `prune/VISION.md`" banner; do not leave
   it reading as a live direction.
6. Add a lightweight "doc currency" note/checklist so a rebuild updates the doc spine in the same pass.

## Files Affected

- `ww_agent/AGENTS.md`, `ww_agent/README.md`, `ww_agent/src/README.md`, and
  `ww_agent/src/{identity,inference,memory,world}/README.md`, `ww_agent/{config,scripts,tests}/README.md`
- `ww_agent/src/loops/README.md` (ensure historical banner is sufficient; no current-doc inbound links)
- `worldweaver_engine/README.md`, `worldweaver_engine/FEDERATION.md`, `worldweaver_engine/CLAUDE.md`
- `prune/v6_docs/*` (archive or banner)
- Root `README.md`, `CLAUDE.md` (verify only)

## Out of scope (explicitly NOT drift to "fix")

- `research/**` — evidence / run records, not guidance.
- `prune/majors/**`, `prune/minors/**` — dated, append-only decision records; historical references are
  correct as of their date. Do **not** rewrite history.
- `prune/harness/**` — the shared portable kit, also published as the standalone public `prune` repo. Its
  `improvements/` references must be reconciled in coordination with that repo, not unilaterally here.

## Acceptance Criteria

- [ ] `ww_agent/AGENTS.md` points new agents at the current substrate, not the superseded loops README.
- [ ] No guidance/README surface (engine + agent, excluding the scoped-out sets) describes removed files
      (`loops/{fast,slow,mail}.py`, old `memory/` tiers, `tuning.json`) as current.
- [ ] `improvements/` no longer appears as a live path in engine guidance docs or the `CLAUDE.md` shim.
- [ ] `prune/v6_docs/` is either archived or banner-marked superseded against `prune/VISION.md`.
- [ ] A doc-currency note exists so future rebuilds keep the spine honest.

## Risks & Rollback

- **Over-deletion of useful history.** Prefer historical banners over deletion where a doc has archival
  value (the loops README is the model). Rollback is git.
- **Cross-repo divergence.** Touching `prune/harness/` here would fork the standalone `prune` kit — left out
  of scope on purpose.
- **Soul/identity docs.** If any per-resident identity prose is encountered, treat as canonical (Major 68's
  caution) — out of scope for this doc-drift pass.

---

*Created 2026-06-16 from the public-repo cleanup reconnaissance. Recon complete; rewrite deferred.*
