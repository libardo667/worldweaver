# Reciprocity: edge-based vs windowed — verification run

**Date:** 2026-07-14
**Purpose:** Major 66 acceptance criterion #3 — does the Major-66 reply-edge metric
(`in_reply_to`, perceived-conditioned, zero window) agree with the windowed turn-taking
heuristic on a frozen run?
**Tool:** `research/probes/reciprocity.py` (last touched f113476, 2026-07-13)
**Repo commit at run time:** 5a3fea9
**Data (gitignored, local-only runtime state):** `shards/ww_pdx_deal/residents` (47 people),
`shards/ww_pdx_keep/residents` (15 people). Observed motion: deal 238 moves, keep 4 moves
(consistent with deal = venture-ON, keep = venture-OFF; label inferred from motion, not asserted).

## Recompute command

```
python3 research/probes/reciprocity.py shards/ww_pdx_deal shards/ww_pdx_keep
```

(from repo root. The probe's default `--residents ../shards/...` is stale post-Major-83; pass
explicit cohort roots — a cohort root is a dir containing `residents/`.)

## Numbers

| metric | deal (ON) | keep (OFF) |
|---|---|---|
| speaks | 168 | 228 |
| person-addressed | 155 | 91 |
| moves | 238 | 4 |
| **windowed turn-taking @5min (REAL)** | 31.0% (48) | 14.3% (13) |
| — vs shuffle null @5min | NULL 1.7%, z +26.4 | NULL 5.9%, z +3.6 |
| — dyads / top-dyad share @5min | 4 / 60% | 6 / 31% |
| **edge-based perceived-conditioned (zero window)** | 70.0% (7/10) | 20.4% (10/49) |
| — perceived overtures-to-self (power gate ≥20) | **10 — INCONCLUSIVE** | 49 — conclusive |
| — dyads / top-dyad share | 4 / 29% | 7 / 40% |

## Verdict (criterion #3)

- **keep (conclusive):** edge-based 20.4% vs windowed@5min 14.3% — same direction and rough
  magnitude; both clear the null (z +3.6). The edge-based number is the window-free one. **Agreement
  within the noisy band; criterion #3 met for this cohort.**
- **deal (underpowered):** only 10 perceived overtures-to-self across 47 residents (gate = 20), so
  the edge metric is **INCONCLUSIVE** and cannot be compared to the windowed 31.0%. This is itself a
  data point: despite 155 person-addressed utterances, almost none register as *perceived direct
  overtures with a stable id* on the addressee's side. Per-capita perceived-overture density is far
  lower in the high-motion cohort (deal 10/47 ≈ 0.21) than the stationary one (keep 49/15 ≈ 3.3).

## Caveats bounding these numbers

- **Ledger truncation.** `ww_agent/src/runtime/ledger.py` caps each resident ledger at
  `_MAX_EVENTS = 10000` (front-truncating). These cohorts are far under the cap (≤ a few hundred
  speak events each), so no truncation here — but any long continuous run would silently window the
  ledger and bound reciprocity to the last 10k events. (Flagged as a separate substrate concern.)
- **Cohort semantics** (deal=ON / keep=OFF) are inferred from the motion split, not read from a
  logged `cohort_config` — which is exactly the Phase-3 provenance gap Major 66 still has open.
- **Source data is gitignored** (`shards/*/residents`); this file is the tracked recompute record.

## Re-open trigger

Re-run if `reciprocity.py:perceived_conditioned` (`:63-110`) changes, or on any run where the
per-capita perceived-overture density on a high-motion cohort clears the ≥20 gate (which would let
the deal-side edge-vs-window comparison actually resolve).
