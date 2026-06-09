# Gate A — re-pin at D2 + Q2 axis + A4 figure (round-9 fixes closed)

Closes three of the round-9 cold-review items. All portraits scripts are now snapshot-aware
(`--snapshot` or `SNAPSHOT=` env) and re-run against the **D2 freeze** (`D2-checkpoint/`, 1,213 keeps) —
the state the swap actually departs from, not the 930-keep / 15:03Z maturation snapshot the scripts
previously read.

## Q2 axis — pinned on ONE axis; hub corrected to Ari Rosenbaum

`portraits/connectivity_rank.py --snapshot ../D2-checkpoint`. The A/B takes the two extremes of a single
**composite connectivity axis** = (reciprocated dyads, strong dyads, in-degree, in-mass):

- **ISOLATE (control) = composite MIN — Mateo Villanueva:** 0 recip, 0 strong, in-deg 6, in-mass 14.
- **HUB (treatment) = composite MAX — Ari Rosenbaum:** 10 recip, 4 strong, in-deg 11, in-mass 52.

The earlier prose called **Amir** the hub — wrong: Amir is the *in-mass* maximum (66) but only 7
reciprocated, mid-pack on the composite. Mixing the in-mass-max (hub) with the composite-min (isolate)
was the round-9 catch. Fixed: one axis, both ends from it. (Amir remains the **drive-injection pilot**
subject for §A2 — a *separate* control on his Nike Girl family — but is **not** the hub end of the A/B.)

## A4 figure — unsupported "191/192" replaced by a re-runnable script

`portraits/name_stats.py --snapshot ../D2-checkpoint` (the round-9 NEEDS-ARTIFACT). At D2:
- **819 person-addressed `pulse_act_emitted` acts; 818 (100%) multi-token full-name;** exactly **1**
  bare-ambiguous ("Ari") → flagged, never guessed.
- Homophone trio (Jihoon Cho / Ji-Hoon Park / Jiahao Chen): **3 distinct normalized strings, 100%
  full-name** → `resolve_reference` disambiguates cleanly.
(Counts the *chosen* act target — the unit A1 scores — so it differs from the review's effector-echo count;
the qualitative claim "addresses are resolvable full names" is robust either way. The bare "191/192" is dropped.)

## Re-pin — family characterizations at D2 (structure stable)

`family_reciprocity.py` / `social_groups.py` with `SNAPSHOT=../D2-checkpoint`. Cohesion is unchanged from
the maturation snapshot, numbers slightly higher: Nike Girl 6/6 (5 strong), Division/Clinton 5/6 (5),
South Waterfront 6/6 (4), **Insignia 3/6 (1 — still the loose cluster)**; Mateo still 0-reciprocated.
**These D2 figures supersede the 930-snapshot numbers cited in the field guides** (qualitative structure
unchanged; the guides' prose stands, the quantitative record is now D2).

Remaining gates before the swap: B (D1 from the ledger + K), C (KEEP record), D (parity 16/16 on D2),
E (baseline-variance calibration).
