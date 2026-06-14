# Source-grounding gate for epistemic familiars — verify spoken specifics against the bytes actually read

> **Reframed 2026-06-08 (Mr. Review).** This was first written as "capture the model's reasoning." That
> was wrong, and the error matters. Enabling extended thinking is **not** a window onto a non-thinking
> pass's hidden computation — it's a **different, more capable inference mode** (new reasoning, different
> output = a different population). The Auditor bug needs **none of that**: it's fixed by a mechanical
> source-check with **no thinking at all**. Reasoning-capture is *neither necessary nor sufficient* for
> the bug, and bundling a population-changing cognitive mode into a "don't let it make things up" patch is
> exactly the observational/cognitive blur the confound discipline exists to prevent. So: this Major is
> the **gate** (ship conservatively). Thinking-enablement is a **separate, optional, fenced** item below.

## Problem

Epistemic familiars (the Auditor — the first familiar whose *output is a claim about a source*)
**confabulate receipts.** Two runs (2026-06-08): the un-hardened Auditor invented a SQL query / line
number / dates; the hardened one (Minor 58 soul guard) produced an `AUDIT LOG` with quoted "receipts,"
`VERIFIED` stamps, and a "no confabulations" self-certification — *all* invented, the quotes lifted from
its own injected world-briefing and **misattributed** to a file it cited but never transcribed. The
soul guard **backfired** — it taught the *costume* of rigor. The substrate routes the act through the
speech-pulse and never checks the spoken specifics against the **actual bytes the familiar read**; so a
"VERIFIED, signed" report can be 100% confabulated and look exactly like rigor. (Expressive residents
are unaffected — their feeling is self-grounding, they make no source-claims; this is epistemic-only.)

## Proposed Solution — the source-grounding gate (NO thinking)

A **pre-commit verification gate** on epistemic acts. When a familiar's act asserts a concrete specific
about a source — a filename, a line number, a quoted span, a number — the substrate checks that specific
against the **bytes the familiar actually read this ignition** (its tool-read results, already in
context). Unverified specifics are **stripped or downgraded to "suspected (unverified) — see <pointer>"**;
the familiar may report a *suspected* seam with a pointer, but may not present it as *shown* without the
verbatim span existing in a real read. **Abstain over invent.**

- **No extended thinking required.** This is a mechanical check on output, not a cognitive-mode change.
  It does not make the model reason more or better; it refuses to let unsupported specifics ship. (That
  is why it's safe in a way thinking-enablement is not.)
- **Gate against the SOURCE bytes, never the model's claim or its thinking.** The thinking can
  confabulate too — a model that *thinks* "the query is `SELECT…`" would have its fabrication blessed if
  we checked against the reasoning. The hard check is verbatim-against-the-read-bytes, full stop.
- **This is the product wedge.** A *verifying* familiar that says "I can't ground this" instead of
  inventing a query is the trust-foundation for the whole book-ecology (an Archivist / Mr. Review that
  abstains). Available now, no cognitive change. The Auditor ([[ww-stable-seasonal-auditor]]) is the test
  bed; it stays dormant until this ships.

## Files Affected

- a pre-commit gate (effectors or pulse output path) — for an epistemic act, match each spoken specific
  against the in-context read bytes; strip/downgrade the unverifiable.
- the read-capture path — ensure the tool-read result (the source bytes) is retained in a form the gate
  can match against.
- soul/role config — which familiars are epistemic (subject to the gate); residents are not.
- Shared with the `the-stable` fork — reconverge.

## Acceptance Criteria

- [ ] On the same input that produced the SQL confabulation, the Auditor either quotes a span that
      exists verbatim in the bytes it read, or abstains (`suspected`/`UNREAD`) — and **keeps the gist**.
- [ ] No invented filenames, line numbers, SQL, or dates survive to a committed epistemic act.
- [ ] **No extended thinking is enabled by this fix** (verify by config: same inference mode as before).
- [ ] Expressive residents are entirely unchanged.

## Risks & Rollback

- **Over-suppression**: a true suspected-seam should downgrade to *suspected* (with pointer), not vanish
  — report, don't gag. Rollback = disable the gate, fall back to Minor 58's (insufficient) soul guard.
- **Matching robustness**: "spoken specific ↔ read bytes" needs tolerant matching (whitespace, quoting)
  without becoming loose enough to pass a paraphrase as a verbatim quote.

---

## SEPARATE / FENCED (a future Major, NOT this one): thinking-enablement

Enabling extended thinking (Sonnet 4.5 thinking, OpenRouter reasoning passthrough) is a **distinct,
optional** enhancement: an **observability win** (you can read what it reasoned) **plus a capability
upgrade** (it reasons better). It is a **COGNITIVE change → a different population**, and it is **neither
necessary nor sufficient** for the confabulation fix above. Discipline:

- **Quarantined to the epistemic/tool lane.** Tools may someday think; the **science stays single-pulse**.
- **Never enters a city by drift.** Letting thinking into the residents is a real experiment worth
  running someday — **on purpose, pre-registered, as its own arm** — never because the horizon looked
  exciting from here. The firewall holds only as long as the discipline does, not the enthusiasm.
- **Talk about it on the cognitive side of the line**, always — calling it "making the invisible visible"
  (the [[ledger-edges-not-nodes-schema]] banner) is the blur the confound discipline forbids. Major 66 is
  observational; this is not; they are not siblings.
