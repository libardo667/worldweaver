# Pen-vs-Substrate perception-replay harness — DESIGN

Tests the project's load-bearing claim: *the self lives in the soul + ledger + kept memory,
not the runtime LLM ("the pen") — the pen is swappable.* We already know the pen owns the
**surface** (theme, register). The open question is whether it also owns the **deep self** —
what a resident remembers and whom it bonds with — measured **over time**, not at a frozen instant.

## The counterfactual
Take a cohort matured under one pen (KEEP). Record each resident's exact lived experience. Then
replay that **byte-identical experience** into copies running on a different pen, and measure
whether a swapped pen, given an identical life, **keeps different memories and forms different
relationships.** That is the operational meaning of "swappable pen": same life in, same person out.

Why replay (not a free-running A/B, and not a frozen probe):
- A **free-running** A/B is a closed feedback loop — each pen produces different utterances →
  different perceptions → the two arms drift into different rooms, so the primaries get measured
  against divergent opportunity sets (worse the longer it runs). [killed v1]
- A **frozen-instant** probe holds the perception, the recalled memory block, and the drive vector
  identical across arms — three of four pen-independent — so it can only measure "does the pen read
  its own prompt," structurally biased toward THESIS-HOLDS, and blind to *curation over time*. [killed v2]
- **Perception-replay** holds the *external* opportunity set constant (by replay) while letting
  *internal* curation compound (tick-1's pen-specific keeps change tick-2's recall). It measures the
  thing the thesis is actually about.

## The run set
| arm | pen | role |
|---|---|---|
| **KEEP** | pen-A | the recorded life (live run) |
| **KEEP′** | pen-A | same pen, replayed — the **stochastic noise floor** (LLMs are random even on identical input) |
| **SWAP-B** | pen-B | different pen, replayed — the test |
| **SWAP-C** | pen-C | second different pen — replication (capability ≠ self; a single-pen collapse is inconclusive) |

Read = `divergence(SWAP, KEEP)` **vs** `divergence(KEEP′, KEEP)`. SWAP counts as real divergence only
if it exceeds same-pen noise, across ≥2 pen-pairs.

## Architecture — record/replay at the HTTP choke points (zero production change)
Every world interaction funnels through three methods on `WorldWeaverClient`: `_get`,
`_get_with_retry`, `_post` (`src/world/client.py`). The harness subclasses just those:

- **`RecordingClient`** (live KEEP run): passes calls through to the real backend and tees each
  (kind, path, params/payload, status, body) into a JSONL recording, tagged by tick.
- **`ReplayClient`** (KEEP′/SWAP): serves recorded **read** bodies (per `(method, path)` FIFO, in
  recorded order); **captures-and-suppresses writes** (a swapped pen's acts are logged but must not
  mutate the fixed, recorded world); a read with no recorded match is served `{}` and counted in
  `misses`.

Because replay happens **below** `perceive()`, the real `perceive()` genuinely runs on replay — so
its substrate side-effects (heard→social_pull, ambient→vigilance, the packets that drive arousal and
ignition) are reproduced for free. And each read method parses its own dataclass from `resp.json()`,
so replaying raw bodies lets the **real, unmodified client** do the parsing. `CognitiveCore` takes
`ww_client` as a constructor arg, so the swap is "hand it a `ReplayClient`" — nothing in the
production perception/cognition path changes.

## Faithfulness boundary (state it plainly; the reviewer will probe it)
- **Held constant:** the per-resident perception stream (served from the recording).
- **Free to diverge:** internal curation — what each pen chooses to keep (`memory_kept`) and whom it
  answers (`in_reply_to` edges).
- **Known limitation — "dreaming through KEEP's day":** a swapped resident receives KEEP's recorded
  perceptions regardless of how its own (suppressed) actions differ. So a SWAP resident that "would
  have" moved elsewhere still hears KEEP's room. This is the correct counterfactual for "is the
  durable self pen-robust given identical experience," but it means SWAP divergence is measured
  against a *fixed* world, not a reactive one. Off-recording reads (`misses`) quantify how far a
  swapped pen strays — reported, not hidden.
- **Embedder is not swapped:** recall/drive run on the same embedder in all arms (by construction),
  so any divergence is the *pen's*, not the retriever's.

## The parity check (gates everything — no result counts until it passes)
Replay KEEP's own recording with KEEP's own pen and confirm the **deterministic** substrate matches
the live KEEP run tick-for-tick: arousal, surprise, the `recalled` set, and the emitted packets. The
**pulse output will not match** (it is stochastic) — and that mismatch is exactly the KEEP′ noise
floor we need. If the deterministic substrate diverges, the keying/replay is unfaithful and must be
fixed before any divergence number is trusted. Off-recording `misses` on a same-pen parity replay
must be **zero**.

## What gets measured
- **Pilot (this cohort: armC):** memory-curation divergence — overlap/distance of the `memory_kept`
  sets across KEEP / KEEP′ / SWAP. (armC is topic-monoculture and relationship-sparse, so it is a
  fair substrate for the *memory* half only — the *relationship* half is gated to a later, less
  convergent cohort.)
- **Later (fresh cohort):** relationship-curation divergence — overlap of formed `in_reply_to` edge
  sets, with the pre-registered KEEP-baseline floor (if KEEP's own relational signal doesn't clear
  its null, the run is INCONCLUSIVE, never THESIS-FALSE).

## Status
- [x] Record/replay choke-point layer + offline round-trip proof (`tests/test_pen_swap_replay.py`,
      no server: record via httpx MockTransport → replay → real client parses identical dataclasses;
      writes captured; misses counted).
- [ ] Rehydrate a matured armC resident dir from public artifacts (`research/runs/2026-06-08-armC-ab/`).
- [ ] Live KEEP recording (short) → replay driver → **parity check**.
- [ ] KEEP′ + SWAP×2 → memory-curation divergence → desk packet.
