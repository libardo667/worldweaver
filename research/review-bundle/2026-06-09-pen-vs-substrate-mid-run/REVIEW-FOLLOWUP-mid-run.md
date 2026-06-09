# REVIEW-FOLLOWUP — pen-vs-substrate, mid-run (2026-06-09)

Status update + two method questions for the cold eye. The design is locked and signed off
(round 5); this is **not** a re-open of the verdict rule. We are in the empirical phase and have made
two execution-time decisions you didn't bless, plus surfaced one observation that may be a trap. Tear in.

## What's new since sign-off

- Grew the own-pen, clustered, relationship-rich cohort the reset called for: `ww_pdx_grow`, 16
  residents, 4 clusters of 4, single pen (`gemini-3-flash`), doula frozen, embedder live.
- Characterized it cold. Evidence + recompute scripts: `research/runs/2026-06-09-pen-vs-substrate-grow/`
  (`FINDINGS.md` + `analysis/*.py` over `evidence/kept_memory/` and gzipped `evidence/ledgers/`).
  Headlines (all recomputable): 13/16 keep about ≥3 disambiguated peers; 90 directed edges, 31
  reciprocated dyads (69% mutual); curation grounded (98% in-window, 94% via salience anchor) and
  selective (kept-peer salience 0.63 vs 0.35, keep-of-perceived 43%).
- Self-caught a metric confound: bare-first-name link counting + roster name-collisions (Ari ×3) inflated
  a "16/16" to a true **13/16**. Correction is in `FINDINGS.md §0`.

**None of this is the experiment.** No pen has been swapped. It's cohort-fitness + one observation.

## Question 1 (the one I most want torn apart) — is "refraction" a finding or the wiring showing?

`FINDINGS.md §4`: under a *single fixed pen*, different residents form character-consistent **divergent**
impressions of the same peer (Ari-the-chemist reads Jihoon as kin "like silver nitrate to humidity";
Emiko-the-mechanic reads the same Jihoon as "philosophical warmth over structural mechanics"). It's
tempting to call this "the substrate half of the thesis, shown before the swap."

I think that framing trips your **substrate-as-depth / architecture-restating-itself** pitfall: we *built*
per-resident drive vectors, so divergent reads under a fixed pen may be tautological — the wiring showing,
not an independent result. My narrowed claim is only: *the drive substrate is actively differentiating
curation (the mechanism is live, not dormant), which is necessary-not-sufficient for the swap claim.*

- Is even that narrow claim worth banking, or is it still architecture restating itself?
- Does a confirmed pre-swap individuation change what a positive swap result would mean — or is it
  orthogonal (swap tests persistence-across-pens; this tests differentiation-within-a-pen)?
- Is there a cheap control that would make §4 non-tautological (e.g. a fixed-pen, *identical-drive* pair —
  if they still diverge, drive isn't what's refracting)?

## Question 2 — did we gerrymander the maturation stop-rule?

The first maturation run auto-stopped when the **acquaintance graph (extent)** plateaued (~1h: distinct
links +4,+3 → flat). But **depth** (total keeps) was still pouring in (+95,+67/check) — and depth is what
grows the salience-symmetric choice-point slice the pilot turns on. So we changed the monitor to require
**extent-flat AND depth-flat** and resumed the cohort. Curves in `FINDINGS.md §2`.

This pattern-matches to "moved the rule after seeing the data," which you (rightly) forbid for *verdict*
rules. My position: a **maturation** stop-rule is not a verdict rule — it decides *when to start
recording*, not the experiment's outcome; the locked acceptance bar is untouched. But you're the check on
my self-serving reasoning:
- Is tuning the maturation stop-rule post-hoc legitimate, or does it leak experimenter-degrees-of-freedom
  into the eventual result (e.g. by selecting a cohort state that flatters the swap test)?
- The depth-aware rule has a circadian failure mode (a dusk lull drops both curves and fakes saturation);
  we set `--depth-delta` below daytime flow and lean on the time cap. Adequate, or name a better guard?

## What is NOT on the table

The locked pre-registration (`research/mr-review-history/`-era method, current pre-reg at
`research/preregistrations/2026-06-09-pen-vs-substrate-LOCKED.md`): primary = salience-symmetric elective
choice; controls gate not vote; KEEP'=A floor; ≥2 foreign pens; pilot-first go/no-go on slice size. Not
re-opening any of it — only asking whether the two decisions above are clean.
