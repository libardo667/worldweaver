# Gate B — D1 reconstruction + the A1-elective slice + K (round-9 Q3 closed; pilot GO)

## D1 reconstructed from the truncated LEDGER (not kept_memory alone)

`D1-checkpoint/` = the D2 ledgers + keeps truncated to `ts ≤ 2026-06-09T12:32:00Z`. **549 keeps** (matches
the review's count). The ledger is front-trimmed (earliest retained ts ~10:54–11:37Z per resident), so D1's
**conditionable window** is the ~90-minute retained tail → 12:31Z, NOT D1's full nominal 09:47→12:32 span.
The window is *usable*, not empty: **334 in-window speak-acts, 1,142 anchor observations.** Per the review:
recall stays exact (salience query over never-trimmed kept_memory) and arousal/afterimage re-derive over
the retained tail; the casualty is only the pre-~11:00 salience-conditioning, which trims the window, not
generic "noise."

## The A1-elective slice (`portraits/choice_points.py`) — pilot go/no-go = GO

Salience-symmetric elective choice points (≥2 established-peer candidates salient; addressed one; the
addressed peer was NOT the strict salience-max, so the substrate/relationship plausibly broke the tie —
full definition + pre-registration caveats in the script docstring):

| depth | speak→established | elective (≥2 cand) | **salience-symmetric** | residents ≥1 |
|---|---|---|---|---|
| D1 | 173 | 167 | **111** | 14/16 |
| D2 | 761 | 739 | **561** | 16/16 |
| D2 (band 0.34) | 761 | 739 | 645 | 16/16 |

**The slice is abundant, not thin.** The meta-finding's worry ("the falsifiable residual is too thin for a
strong claim") is refuted: hundreds of salience-symmetric choice points across near-full cohort coverage at
both depths. This is the GO branch — run the swap; do NOT bank the architecture-vests result by default.

## K — pinned a priori (frozen before any swap data)

**K = ≥5 salience-symmetric elective choice points per scored resident AND ≥10 scored residents, per
depth.** Below K at a depth → that depth is **INCONCLUSIVE, never FALSE** (round-9 Q3). Both depths clear K
comfortably in this proxy (D1: 14 residents, ~8/each; D2: 16, ~35/each).

## Scope caveat (for cold review)

These counts are from the **maturation ledger** — a proxy for the slice the experiment actually scores,
which is captured fresh at **KEEP-recording time** (Gate C, `record_run` + `RecordingClient`). The proxy
shows the cohort *generates* symmetric-elective choices densely, so the KEEP recording will yield a
comparable slice; **K is re-checked on the real KEEP slice**, and D1's slice will come from its ~90-min
conditionable tail. The salience-symmetry band is a pre-registration choice (default 0.0 = addressed not
the strict unique max; reported also at 0.34) — flagged for the reviewer to pin.

Gate B closed. Remaining: C (KEEP record at D1+D2), D (parity 16/16 on the D2 recording), E (baseline-variance).
