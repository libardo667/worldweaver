# Soul-domain retention across the world-event boundary (the discriminator)

> **Disposition: implementation complete; archived 2026-07-14.** The reusable metric, verdict, tests,
> and go/no-go framing satisfy all three acceptance criteria. Applying it to a newly run storm boundary is
> a separate empirical activity and is deliberately not kept as architectural implementation debt.

## Metadata

- ID: 57-soul-domain-retention-measurement
- Type: minor (measurement / experiment, not a runtime change)
- Owner: Levi
- Status: backlog
- Risk: low
- Depends On: a live shard run spanning a world-condition boundary (a storm starting and stopping)

## Problem

The live SFO run showed individuated voices all converged on one topic (the storm's drainage). Mr. Review: the **acute** shared-event response is *realistic* (a city in an 18-mph storm does all watch the rain); the **disease** is the *promotion and persistence* of it, not the acute convergence — and the gate is off, so nothing has promoted. The discriminating evidence is therefore the **post-storm snapshot**: when the rain stops, does each mind keep its distinctive (soul-sourced) anchors above the shared-event floor (does Santiago return to flowers — **addition**), or does the shared topic crowd them out (just drainage — **displacement**)? Santiago still bridges "floral hydraulics → drainage" (early in the slide); Delia has dropped the bridge (pure infrastructure, displacement). This metric is the empirical discriminator between healthy individuation-on-a-shared-topic and semantic monoculture — and the validation for Majors 60 and 61.

## Proposed Solution

A measurement (no runtime change): re-wake the shard, run it across a world-condition boundary (or replay one), and compute **soul-domain retention** per resident — the fraction of each mind's distinctive, soul-sourced anchors/themes still above the shared-event floor, sampled **before / during / after** the event. *Addition* = the soul-domain holds through the event; *displacement* = the shared topic crowds it out and it doesn't return.

## Files Affected

- a measurement script (reads resident ledgers' anchors + staged self-deltas across the boundary; compares to each soul's distinctive domain).
- (no runtime change.)

## Acceptance Criteria

- [x] A per-resident soul-domain-retention metric across a world-event boundary (before/during/after). — `scripts/soul_domain_retention.py`: `soul-domain share` per window = salience-weighted fraction of a mind's anchor-attention on its own soul-resonant domain (`anchor_observed` sets × `DriveVector` resonance with the canonical soul).
- [x] A clear read: do minds return to their own domains post-event (addition), or stay displaced (monoculture)? — per-resident `addition` / `displacement` / `partial` / `no-baseline` verdict from the after/before share ratio, plus a population tally.
- [x] The result feeds the Major 60/61 go/no-go (is the convergence acute-and-realistic, or promoted-and-persistent?). — the script prints the go/no-go framing; **the live read still requires a real storm-boundary run + the real embedder** (see status).

## Status

**Built 2026-06-06** (measurement script + 3 synthetic unit tests). Runs end-to-end against the existing SFO ledgers; the testable core (`resident_retention`) is covered by a controlled-embedder unit test that separates addition from displacement. **Not yet a real read:** needs (a) the actual storm-boundary timestamps (`--event-start/--event-end`; absent, it splits the anchor span into thirds) and (b) `WW_EMBEDDING_URL` set — the offline `DeterministicEmbedder` hash-collides unrelated words (storm ≈ flowers), so its output is structurally valid but semantically meaningless. `SOUL_DOMAIN_THRESHOLD` (0.18) is a starting dial to tune against a real run.

## Validation Commands

- `(manual) re-wake the shard across a storm boundary; run the retention script; read the before/during/after.`

## Risks and Rollback

- Risk: low — a read-only measurement.
- Note: needs real runtime spanning a world condition; can't be shortcut to a unit test.
