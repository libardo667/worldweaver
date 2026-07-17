# Cost before/after — loop-era vs substrate (analysis + chart)

> **Canonical home: WorldWeaver. Legacy Stable ID: Minor 47.** Migrated 2026-07-14 and retained as
> low-risk offline analysis, outside the immediate architecture queue.

## Metadata

- ID: 120-cost-before-after-loop-era-vs-substrate
- Type: minor
- Owner: Levi
- Status: backlog
- Risk: low

## Problem

There is strong, grant-grade cost evidence sitting unprocessed in two OpenRouter activity exports (root `openrouter_activity_2026-06-03.csv` and `…06-04.csv`), but it has only been characterized ad hoc in conversation, never turned into a durable analysis or a chart:

- **Loop era (Mar 2026):** ~**$355 over 24 days**, peaking **$86/day** and **233k calls/day** — the four cognitive loops polling per-resident-per-loop continuously (gpt-oss-120b 410k calls + deepseek 166k), plus discretionary premium-model testing (`(none)` key, ~$133, claude-sonnet at $167/k-call).
- **Substrate familiars (Jun 2026):** ~**$0.17/hr (~$4/day)** for all five cloud familiars, ~37 calls/hr — the pulse is ignition-gated, so cost scales with *surprise*, not wall-clock.
- **Local floor:** $0 marginal (Rung-1 / Pocket Lab).

The honest decomposition matters: the win is structural (poll-vs-ignite), and a chunk of March was discretionary premium testing, not runtime. This is the single most concrete efficiency story the project has, and it feeds Major 53 (grant pack) and world-weaver.org.

## Proposed Solution

A small, reproducible analysis script over the OpenRouter exports that produces: the daily cost/volume curve, the per-key/per-model decomposition, the poll-vs-ignite call-rate contrast, and a clean before/after chart (PNG/SVG). Keep the honest caveats inline (runtime vs discretionary testing; the loop-era data does contain the real comparison, contra an earlier wrong claim that it didn't).

## Files Affected

- `research/probes/cost_curve.py` (extend the existing cost tooling, or add a sibling analysis script)
- a generated chart artifact (PNG/SVG) under a documented path (feeds `prune/`)

## Acceptance Criteria

- [ ] One command regenerates the daily cost+volume curve and the per-model decomposition from the CSVs.
- [ ] A before/after chart (loop-era vs substrate) is produced as a durable artifact.
- [ ] The runtime-vs-discretionary-testing split is stated, not hidden, so the figure is defensible.
- [ ] Output is grant-ready (the numbers cross-checked against the raw CSVs).

## Validation Commands

- `python dev.py run research/probes/cost_curve.py …` (or the new analysis script over the CSVs)
- `(manual) eyeball the chart + reconcile totals against the CSV rows`

## Pruning Prevention Controls

- Authoritative path: the OpenRouter CSV exports are the source data; the script is pure read.
- Parallel path introduced: none.
- Artifact output target: a documented chart path (referenced by Major 53); not committed if large/binary per repo policy.
- Default-path impact: none (offline analysis).

## Risks and Rollback

- Risk: misattributing discretionary testing spend as runtime cost (overstates the win). Mitigate by keying on `api_key_name` + model.
- Rollback: delete the artifact; no runtime impact.
