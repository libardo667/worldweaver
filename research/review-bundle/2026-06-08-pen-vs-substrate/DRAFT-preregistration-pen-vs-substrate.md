# Pen vs Substrate — PRE-REGISTRATION (DRAFT — pre-mortem requested BEFORE lock)

*Not locked. This is a draft handed to Mr. Review for a pre-launch pre-mortem. Predict the
outcome, attack the design, name the confound I missed — THEN we lock and run. Nothing has
been spent.*

## The thesis under test (the project's load-bearing claim)
`CLAUDE.md`, verbatim: **"The self lives in the soul + ledger + kept memory, not the model
(the model is a swappable pen)."** This is the foundational premise of the whole architecture
and it has never been tested. It is falsifiable: swap the pen out from under a *matured*
resident — if the self lives in the substrate, the self persists; if the self was the model,
it doesn't.

## Why the question is sharp, not trivial (raw)
The pen and the affect substrate are **already two different models**:
- The **pen** = the pulse/inference model, `WW_INFERENCE_MODEL` (default `google/gemini-3-flash-preview`).
  This is what turns self-inputs into utterances/acts. [`ww_agent/src/main.py:106`,
  `runtime/pulse_engine.py:293-345`]
- The **affect substrate** = the drive vector, computed by a *separate* embedder
  `WW_EMBEDDING_MODEL` (`nomic-embed-text`), read from the resident's own identity slices —
  **not** the pulse model. [`runtime/drive.py:1-19`, `runtime/cognitive_core.py:75`]

So "swap the pen" = swap `WW_INFERENCE_MODEL` only; the drive/affect substrate is **untouched**.

We already know the pen owns the **surface** (Skeptic's Desk open-Q #1, raw): same cold Portland,
same diverse cast, swap only the runtime model → theme goes `gemini`→"integrity of the foundation"
vs `claude-haiku`→"restless weight of unanswered calls"; VOICE retention 0.92→0.73; CONTACT 30%→0%.
No model came out theme-neutral. **Established: the pen owns the surface.** The open question is the
flip: **does the pen also own the DEEP self — its memories and its relationships?**

## The axis decomposition (the core design move)
Three classes of feature, assigned BEFORE the run:

| class | axes | prediction | role |
|---|---|---|---|
| **MODEL-CARRIED** (pen owns it — proven) | dominant theme; register / opener-template | MUST shift SWAP-vs-KEEP | **positive control** (proof the swap "took") |
| **SUBSTRATE-CARRIED** (thesis claims pen does NOT own it) | relationship fidelity (dyads); memory continuity (cites own past) | thesis: PERSIST · anti-thesis: COLLAPSE | **primary signal** |
| **CONSTRUCTION-FIXED** (held by wiring, not the pen) | drive vector / affect | persists by construction | **EXCLUDED — not evidence** |

The drive vector is **excluded on purpose**: the embedder isn't swapped, so its persistence is the
architecture restating itself, not a finding (brief §3: "a model discovering a fact you built into
its wiring"). Banking it would be the substrate-as-depth trap.

## Design
Fork a **matured** shard (residents with rich ledgers + established dyads + kept memory) at time T:
- **KEEP** — same pen (`gemini`). Natural-drift control.
- **SWAP** — new pen (e.g. `claude-haiku`), **everything else byte-identical**, isolated DB/ports,
  run forward equal wall-clock from the identical T-state.
- Whole-shard pen swap → **N residents = built-in replication**. If affordable, **≥2 pen-pairs**
  (gemini→claude AND gemini→deepseek) so no single pen carries the verdict.

## Metrics & roles (to be LOCKED at lock; all reuse existing instruments — no new ruler)
- **POSITIVE CONTROL — swap took:** theme/register shift SWAP-vs-KEEP via `analysis/lexical_count.py`.
  No shift → **INCONCLUSIVE (bad swap)**, not a result.
- **CAPABILITY FLOOR — confound guard:** SWAP act-validity rate AND act volume comparable to KEEP
  (within a pre-set band). A SWAP pen that merely emits fewer/malformed acts → **INCONCLUSIVE
  (capability, not self-loss)**.
- **PRIMARY 1 — relationship fidelity:** per resident, fraction of post-fork person-addressed edges
  aimed at its **PRE-fork established peers**, SWAP vs KEEP, scored vs a **degree-preserving shuffle
  null** (reuse `reciprocity.py`). Measures continuity-to-known-peers, not raw dyad existence.
- **PRIMARY 2 — memory continuity:** per resident, reference-count of its **own pre-fork entities**
  (people/places/events drawn from its ledger + kept memory) appearing in post-fork acts, SWAP vs
  KEEP. **Non-embedding entity match** (deterministic), explicitly NOT a "self-similarity" score.
- **EXCLUDED:** drive vector (construction-fixed).

## Verdict rule (pre-registered)
- **THESIS HOLDS (self is substrate-carried):** swap took **AND** capability floor met **AND** both
  primaries in SWAP track KEEP within the noise band.
- **THESIS FALSE (self was the pen):** swap took **AND** capability floor met **AND** the primaries
  **collapse** in SWAP vs KEEP — the new pen forgets the self's people and past.
- **INCONCLUSIVE:** swap didn't take, OR capability floor failed, OR there was no self to lose.

## Known-positive guard (the "inert arm is a void" rule)
Pre-fork, verify each resident is individuated **AND** has **≥K established dyads AND ≥M kept memories**
— a self that *exists to lose*. K, M floors locked at lock. A resident below floor is **dropped**
(nothing to persist → it would silently feed the verdict). This is the internal known-positive the
register round taught us to demand.

## Confound controls / attacks I have already spotted (go deeper than these)
1. **Memory-continuity triviality** — "memory is in the context window, so of course it persists." NOT
   trivial: the pen demonstrably **overrides other in-context features** (theme/register are in the
   context too, yet they shift with the pen). The test is whether it overrides relational/memory
   context the SAME way. A **dissociation** (theme shifts but memory/relationships hold) is the real,
   non-trivial finding; measured against the theme-shift positive control.
2. **Capability confound** — a weaker SWAP pen could just degrade. → capability floor above. (Is a
   floor enough, or does pen-capability leak into the primaries in a way a floor can't catch?)
3. **Relationship-fidelity as population artifact** — controlled by measuring per-resident continuity
   to PRE-fork peers vs the shuffle null, SWAP-vs-KEEP — not raw dyad counts.
4. **Fork cleanliness** — verify clone parity at T=0 (ledger line count, kept-memory count identical
   across arms) before the swap takes effect.
5. **Maturation / n** — known-positive guard + whole-shard N + ≥2 pen-pairs.
6. **Metaphysics overclaim** — claim the **mechanism** ("the substrate constrains the pen on the
   relational/memory axes") NOT "it is the same conscious self." Operational continuity is the proxy,
   not the proof.
