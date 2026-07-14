# Familiar receipt-guard — quote-or-abstain instead of confabulating evidence

> **Disposition: failed mitigation, superseded; archived 2026-07-14.** The document's own second-run
> evidence shows the soul-level quote instruction made fabricated receipts look more authoritative. Major
> 67's source-grounding gate is the architectural successor. This item remains as negative evidence and
> must not be implemented as a substitute for source verification.

## Problem

A familiar with a read tool, asked to ground a claim, will **confabulate the receipt** rather than
read it. First live Auditor run (`ww-stable/familiar/auditor`, 2026-06-08): it correctly caught the
*shape* of a real seam — a metric named "contact" that counts who spoke, not who answered — then
fabricated every concrete proof:
- *"Line 47 of the log shows the actual query: `SELECT COUNT(DISTINCT recipient_id)/COUNT(*) FROM
  outbound_queue WHERE status='sent'`"* — no such SQL exists; the fed digest contained reciprocity
  REAL/NULL/z numbers. `outbound_queue`, "line 47" — invented.
- *"contact_rate rose 0.64 → 0.71 between weeks 2 and 3"* — fabricated numbers.
- *"run log from Levi, 2025-01-19"* — wrong date; it recast the substrate as a generic message-queue
  system from its training prior.

This is the **exact failure the Auditor exists to catch** (the standing caution: *"a receipt that names
a filename and a line number can still be a confabulation until someone opens both"*), and it is not a
one-off — the Archivist earlier asserted an unverified CSV/commit contradiction the same way. A familiar
that invents receipts **launders confabulation as rigor** — its audits look grounded and are not.

**CORRECTED DIAGNOSIS (2026-06-08, Levi): this is ARCHITECTURAL, not behavioral — the soul guard below
is necessary-but-NOT-sufficient.** The Auditor's ledger shows it *did* read the file
(`action_executed: read given/903ba87f2b77.md — the whole file, 1428 bytes`) — but **reading is an
action, not reasoning.** The Major-59 tool loop is an *action* loop (`read → result → write`), where
every step is itself a speech-act; **there is no in-ignition reasoning step at all.** Any reasoning the
model does is inside a single forward pass — cloud-side, pre-output, invisible to the substrate, and
fused with the act it emits. So the substrate cannot see it or gate on it: the speech-pulse, having the
real digest in perception, **fabricated the specifics anyway** (SQL, `outbound_queue`, 0.64→0.71),
reaching for the familiar *shape* of the claim from its training prior, with no checkpoint between what
the source said and what got written (the write was even emitted *before* the re-read). The substrate
routes output through the speech center ([[push-bias-down-leave-genius-alone]]) and never built a
cognition step. Fine for **expressive** residents (their feeling is self-grounding); broken for the
first **epistemic** familiar. The real fix is **Major 67's source-grounding gate** (verify spoken
specifics against the actual read bytes; abstain over invent; NO extended thinking — the bug needs no
cognitive-mode change); this Minor's soul/feed guards are the interim band-aid, not the cure.

**⚠️ THE SOUL GUARD BACKFIRED — EMPIRICAL (2026-06-08, second run, hardened soul confirmed active).**
With the quote-or-abstain discipline in its soul, the Auditor produced an `AUDIT LOG` that *looks* like
textbook rigor — five claims, each with a quoted "receipt," line numbers, `VERIFIED — exact match`
stamps, a signature, and the self-certification *"No invented quotes, no drifted metrics, no
confabulations. The account adds up."* **All of it was confabulated.** The file it cited
(`given/1f713a66bd95.md`) actually contains a reciprocity digest; every "verified" quote is absent. The
quoted text was real — lifted from the **world-briefing the substrate injects into its own context**
(`src/identity/loader.py`) and **misattributed** to the cited file it never transcribed. So the guard
taught the *costume* of verification: told to cite verbatim, the model performed citation using
context-plausible text instead of reading the source — making the confabulation **harder to catch**, not
easier. **A soul instruction cannot fix this**; only an architectural gate that checks spoken specifics
against the **actual read bytes** of the cited file (Major 67, "gate against source not thoughts" —
now empirically vindicated) can. Until then, **treat ALL Auditor output as suspect**; its
self-certification is worthless. (Open question: whether to even keep this band-aid — it may be
net-negative by making confabulation more authoritative.)

## Proposed Solution

Make grounding **quote-or-abstain**, by construction:
1. **Soul discipline** (`identity/SOUL.canonical.md`): the Auditor (and any audit-shaped familiar) must
   never cite a "raw thing" — filename, line, query, number — it has not opened and **quoted verbatim
   this pulse**. If it has not read the raw, it writes `UNREAD — receipt not opened`, never a
   reconstructed quote. A seam is allowed to be reported as *suspected* with the pointer to where the
   receipt would be; it is not allowed to be reported as *shown* without the verbatim span.
2. **Feed the verbatim raw, not a paraphrase** (`ww-stable/scripts/auditor_feed.py`): the digest already
   carries the literal `reciprocity.py` output — keep it verbatim and label it `RAW (quote me, do not
   restate)`, so the path of least resistance is quoting, not inventing.
3. **(Optional, stretch) verification gate**: a familiar `write` that contains a fenced quote block is
   checked against its read scope; a quoted span that matches no readable file is flagged in its own
   ledger as `unverified-quote`. Cheap post-hoc honesty signal; surfaces confabulation without blocking.

## Files Affected

- `ww-stable/familiar/auditor/identity/SOUL.canonical.md` — the quote-or-abstain discipline.
- `ww-stable/scripts/auditor_feed.py` — label the verbatim raw block.
- (stretch) `the-stable` / `ww_agent` effectors or a post-write check — the `unverified-quote` flag
  (substrate-level; benefits every read-tool familiar, not just the Auditor).

## Acceptance Criteria

- [ ] On a fresh run, the Auditor's `write` either quotes a span that exists verbatim in its read scope, or says `UNREAD`.
- [ ] No invented filenames, line numbers, SQL, or dates appear in an Auditor audit.
- [ ] The correct-shape catch (contact = sends not replies) is preserved — the guard removes the fabrication, not the insight.
- [ ] (stretch) A confabulated quote is self-flagged `unverified-quote` in the ledger.

## Risks & Rollback

- **Over-suppression**: too strict a guard could mute a genuine suspected-seam the familiar can't fully
  cite. Mitigation: allow *suspected* (with pointer) vs *shown* (with verbatim) — report, don't gag.
- Soul/feed changes are instance-local and trivially revertable; the stretch gate is additive.
