# grow cohort — mid-run characterization (2026-06-09)

**What this is:** a *pre-experiment* characterization of the single-pen maturation cohort (`ww_pdx_grow`,
16 residents, 4 clusters of 4, pen = `google/gemini-3-flash-preview`, doula frozen, embedder live) for
the locked pen-vs-substrate design. **It is NOT the experiment.** No pen has been swapped. These numbers
describe whether the cohort is a fit substrate to record from, and surface one observation that bears on
the design. Verdict language is deliberately avoided; read every claim as "the data is consistent with."

**Cold-reproducible.** All numbers below recompute from this directory:
- `analysis/relationship_graph.py` + `analysis/growth_curve.py` ← `evidence/kept_memory/*.jsonl` (durable, never trimmed) + `evidence/roster.tsv`
- `analysis/grounding_selectivity.py` ← `evidence/ledgers/*.jsonl.gz` (a ~2h window, ~10:54–12:57; snapshot taken 12:57Z mid depth-stretch)

Snapshot: 16 residents, 608 durable keeps; ledger window ~1140 events/resident.

---

## 0. Metric-confound correction (stated before any headline)

The maturation monitor counts a "peer link" by **bare-first-name** match. The roster has first-name
collisions — **Ari ×3, Layla ×2, Mateo ×2** — so that metric mis-attributes ("Ari" → which of three?)
and can self-link a resident to a namesake. A *per-slug, non-deduped* snapshot reported **16/16**
residents with ≥3 peers; that figure is an artifact. Deduped first-name and clean **full-name**
disambiguation both give **13/16** on this snapshot. The experiment's scorer must use full-name
disambiguation + a self-name guard. (`relationship_graph.py`)

## 1. Structural (durable kept_memory)

- **13/16** residents keep memories about **≥3 distinct** full-name-disambiguated peers.
- **90** directed edges (A keeps about B); **31 reciprocated dyads** (62/90 = **69%** of edges mutual).
- **Locality:** within-cluster 37, cross-cluster 53 → within-fraction **41%** vs chance ~20% (≈2×).
  Co-presence elevates dyad formation above chance, but the global "city" channel has spread acquaintance
  widely (cross now exceeds within as depth accrues) — a fact the design should weigh, not hide.

A random name-drop process does not produce 69%-mutual edges concentrated above chance in the
co-present clusters. The relationships are structured, not noise.

## 2. Two growth curves — EXTENT saturates, DEPTH does not (`growth_curve.py`)

| | first third | last third | shape |
|---|---|---|---|
| NEW links/10min (**EXTENT**, who-knows-whom) | 8.3 | 2.4 | decays → saturating |
| NEW keeps/10min (**DEPTH**, keep-weight) | 34.9 | 34.1 | flat → still flowing |

The acquaintance graph (edge SET) freezes within ~1h; keep-weight (edge WEIGHT) keeps accruing roughly
linearly. **Consequence for method:** a maturation stop-rule on extent alone stops while the signal the
experiment feeds on (keep DEPTH → choice-point slice) is still flowing. The monitor was changed mid-run
to require extent-flat **AND** depth-flat (see REVIEW-FOLLOWUP question 2 — flagged for the cold eye
precisely because it is a stop-rule change made after seeing the first run stop early).

## 3. Curation is grounded and selective (`grounding_selectivity.py`, ~2h ledger window)

The skeptical question: are kept impressions of peers grounded in perception, or pen-confabulated?
Grounding counts a kept peer only via **substrate-side** signals computed *before* the pulse — salience
anchors (`anchor_observed`) and heard packets (`packet_emitted`) — never the pen's own address-target.

- **Grounding:** of 64 in-window kept peers, **63 grounded** (98%); **60 (94%) via a salience anchor**,
  3 heard-only, 1 ungrounded. (Window-bounded → this *under*-counts; keeps whose perception predates the
  window read as ungrounded.)
- **Selectivity:** kept peers carry mean anchor-salience **0.627** vs perceived-but-not-kept **0.352**
  (≈1.8×). Residents perceive ~9.3 peers, keep about ~4.0 (43%). Keeping tracks substrate salience, not
  raw exposure.

**Caveat (the everyone-hears-everyone risk):** two channels exist — `chat_heard` (local) and
`city_chat_heard` (global) — so most peers are perceivable; grounding alone is necessary-not-sufficient.
Selectivity (1.8× salience gap; 43% keep-of-perceived) is what carries the "curation is doing work" read.

## 4. The observation that bears on the design — perspectival refraction (and its trap)

Under a **single, fixed pen**, different residents form **character-consistent divergent** impressions of
the *same* peer. Example (recompute from `evidence/kept_memory/`, target "Jihoon Cho"):
- **Ari Levin** (photographer/chemist) keeps kinship reads — *"speaks in the same logistical shorthand I
  use,"* *"his logic regarding the city's dampness aligns with the way silver nitrate reacts to humidity."*
- **Emiko Tanaka** (structural/mechanics) keeps the same man with disapproval — *"prioritizes philosophical
  warmth over structural mechanics,"* *"mistakes the cooling time of a material for a philosophical dialogue."*
Multiple residents independently converge on Jihoon's core (restlessness/rootlessness, broth, warmth-vs-damp),
i.e. an accurate *shared* portrait, each refracted through the observer's own drive.

**Why this is flagged, not banked:** per the standing brief's "substrate-as-depth / architecture restating
itself" pitfall, this may be **the wiring showing** — per-resident drive vectors were *built in*, so
divergent reads under a fixed pen could be tautological. What it is *consistent with* is that the drive
substrate is **actively differentiating curation** (the mechanism is live, not dormant) — it is **not**
evidence that the self survives a pen swap, which is the only thing the swap run tests. See REVIEW-FOLLOWUP
question 1.

## What is NOT established here

- Nothing about a pen swap (none performed).
- The salience-symmetric **elective-choice-point slice** size — the pilot's go/no-go — is *not* measured
  here; it is captured at KEEP-recording time per the locked pre-registration.
- Section 4 is a hypothesis-shaped observation, not a result; sections 1–3 are cohort fitness, not the claim.
