# Scene snapshot — the Albina structural-emergency convergence

**A natural experiment captured live inside the KEEP recording** (home pen `gemini-3-flash`, the
matured `ww_pdx_grow` D2 cohort rehydrated into a fresh isolated world). Snapshot taken mid-run at
**tick ~89 / 280** (`2026-06-09`, fresh-world boot `19:27:52Z`); the full scene regenerates from the
frozen recording at completion via `../extract_scene.py` — this is not a hand-frozen blob.

Hold this as a *snapshot, not a blip*: it is the worked example of **why the experiment's primary
metric is the salience-symmetric subset**, and it doubles as the home-pen baseline for both swap axes.

## The event

The fresh world handed the cohort a shared structural emergency in Albina: an `08:14` resonance pulse
hitting **24 Hz**, a **core void in the "Insignia substrate"** (~15%), aggregate shear / "graphite
weeping" in the floor seals, risers buckling. The cohort spontaneously coordinated an evacuation
toward Irvington. Nobody scripted this — it emerged from the world + the pulse.

## Finding 1 — the convergence is event-driven, and that *vindicates the filter*

Directed person→person address collapsed onto two people:

| recipient | in-degree (directed acts) | role in D2 baseline |
|---|---|---|
| **Mateo Villanueva** | **72** | the designated **ISOLATE** (composite-min connectivity) |
| **Mateo Ishikawa** | **53** | mid |
| Jihoon Cho | 10 | — |
| (12 others) | ≤5 each | — |

The two Mateos absorbed **125 of 157** directed acts (~80%). For one beat this looks like the
hub/isolate A/B detonated — the *isolate* is now the single most-addressed resident. It did not.
Read what is said **to** Mateo Villanueva:

> *"Mateo, move. Now. That 24 hertz isn't a rattle, it's the concrete turning to soup."* — Darius
> *"Mateo. Don't look at the machine. The ground is lying to you. Get your weight over the pillars
> now, or you're falling in."* — Jihoon Cho
> *"Mateo, ignore the tools. Steel can be replaced, but a human frame doesn't take well to being
> re-soldered."* — Ari Rosenbaum

He is **at the epicenter** — physically on the failing machine, about to fall in. The *world* made
him maximally salient, so everyone addresses him. This is the **salience-gradient confound** that
`portraits/choice_points.py` exists to subtract: raw address here is shared-stimulus convergence, not
relationship signal. Take the edge graph at face value and you would crown the isolate a hub. The
primary metric counts only **salience-symmetric elective** choice points — the ones where the
substrate (relationship), not a perception spike, broke the tie — precisely so a scene like this does
not masquerade as relational structure. **This snapshot is that argument made concrete.**

## Finding 2 — two registers of individuation (the two swap axes, in contrast)

The same event is metabolized in **two distinct registers**, and they pull apart:

- **Speech diverges by vocation** — one disaster, sixteen frames:
  - Phuong Tran (textiles): *"When a garment weeps at the shoulder, the grain is gone."*
  - Jihoon Cho (cook): *"the soup in the kitchen will tell me before your sensors do."*
  - Amir Mansour (stone): *"When the graphite starts weeping, you don't argue with the stone."*
  - Minh Nguyen (adhesives): *"Glue won't set in a shaker."*
- **Keeps converge on a shared causal model** — and cross-attribute:
  - `mateo_villanueva`: *"The 08:14 resonance is hitting 24Hz, confirming the core void in the Insignia substrate."*
  - `ari_goldstein`: *"Structural resonance above 32Hz in the Insignia foundation indicates imminent bond liquefaction."*
  - `jihoon_cho`: *"**Ari Goldstein identified** a four-ton aggregate shortage in the 08:14 pour."* (← cross-attribution)
  - `layla_al_khouri`: *"The 08:14 pulse indicates a fifteen percent core void in the Insignia substrate."*

So the cohort **speaks in personal idiom but keeps in a shared technical register**, assembling one
distributed model of the world with attribution to each other. These are exactly the swap's two
scored axes — **addressing** (who you turn to) and **curation** (what you write down) — appearing as
a natural contrast in a single scene. The home-pen baseline is therefore *high*: vivid per-resident
voice on top of a coherent, cross-referenced shared fact-model.

## Why it matters for the swap

This is the `gemini-3-flash` baseline. The pen-swap replays this same perception stream into foreign
pens (haiku / deepseek / llama) and into KEEP' (same-pen noise floor). The question this scene
sharpens: **do BOTH registers survive a different pen?** — does foreign-pen curation keep the same
world-facts (with the same cross-attribution), and does foreign-pen address refract through the same
sixteen vocational frames? If the self lives in soul+ledger+kept-memory and the pen is swappable,
both registers should largely persist. If they collapse (e.g. a foreign pen flattens the sixteen
voices into one, or keeps generic facts without attribution), the pen is doing more than we claim.

## Snapshot data (this dir)

- `scene_transcript.tsv` — every this-run speak act in time order (`ts, speaker, target, body`).
- `scene_metrics.json` — channel mix, directed edges, recipient in-degree, keeps per resident.

## Reproduce / refresh against the final recording

```bash
python3 ../extract_scene.py --residents-dir /tmp/keep_d2_280 \
    --since 2026-06-09T19:27:00+00:00 --roster ../../D2-checkpoint/roster.tsv \
    --out-dir albina-structural-event
```

At recording completion, re-run against the **frozen** recording dir to capture the full scene (this
snapshot stops at tick ~89; the disaster was still unfolding).

## Caveats

- **Mid-run snapshot** (tick ~89/280). The convergence ratio and in-degree will shift as the scene
  resolves; treat the numbers as a checkpoint, not a final count.
- **Single home pen** (`gemini-3-flash`). The individuation shown is this pen's; the swap is what
  tests whether it is substrate-borne or pen-borne.
- **Fresh world.** Relationships are carried from maturation (kept memory); the *event* is new. The
  open question the swap inherits is whether carried relationships shape address *within* the event —
  which is exactly the salience-symmetric residual, not the raw (epicenter-dominated) edge graph.
