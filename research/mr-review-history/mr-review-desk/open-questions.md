# The Skeptic's Desk — open questions & raw claims

*This is your whole world now, Mr. Review. It was stripped down to this on purpose. You used to read the project's repos and its memory files — its own story of itself — and a reviewer marinated in that becomes a loyalist, not a skeptic. So: claims and raw evidence only. The interpretations the project reached are NOT on this desk, on purpose. **Re-derive the story. Do not inherit it.***

## How to use this desk
- Each entry is a **claim** and the **raw thing** behind it — a number, a file, a run. No narrative.
- When a chapter lands on this desk, test its claims against these. If a chapter asserts something whose receipt is **not on this desk**, that is your first flag: *where is it, and why am I being asked to believe it without the raw thing?*
- If a claim feels obviously true, suspect you've been marinated. You were narrowed for a reason.

## Open questions (unresolved — do not let a chapter pretend these are closed)
1. **Is there any runtime model without a monoculture prior?** RAW: same cold Portland world, same diverse cast, only the runtime model swapped. gemini → dominant theme "the integrity of the foundation" (structural decay), VOICE 0.92, CONTACT 30%. claude-haiku → dominant theme "the restless weight of unanswered calls", VOICE 0.73, CONTACT 0%. No model tested came out theme-neutral. UNTESTED: whether plural/rotating models break the single-model grip.
2. **Does the "venture" mechanism buy engagement, or just more outward talk?** RAW: the metric the project called CONTACT computes outwardness (person-addressed / total speaks), with NO reciprocity term. A windowed turn-taking re-read of THREE frozen venture-ON cohorts (instrument `reciprocity.py`, ledgers attached) — A→B answered by a later B→A:
   - `on_argmax` (gemini seed, full doula): outwardness 39.6%, turn-taking@5min **0.5%** (1 exchange, 1 dyad), @60min 9.1%.
   - `gemini_handonly` (gemini seed, hand-only): outwardness 53.4%, turn-taking@5min **28.2%** (51 utts, 6 dyads, top dyad 35% — a ~4-mind clique), @60min 32%.
   - `claude_handonly` (claude seed, hand-only): outwardness 92.0% and the MOST moves (42), turn-taking@5min **5.6%** (11 utts, 3 dyads, top dyad **82%** = one couple), @60min 15.8%.
   So "reciprocity" spans 0.5%→32% by window×cohort; the earlier "1–5%" was `on_argmax` at a tight window only. The three cohorts are CONFOUNDED (seed model AND doula mode AND run all differ — not a controlled comparison). "Reverse pair exists at all" = ~16–17% across all three. NO venture-OFF control arm has ever been run (no matched venture-OFF cohort was ever frozen); one is about to run, varying ONLY `WW_ACTION_TENDENCY`.
   **NULL ADDED (degree-preserving target-shuffle, 400 draws, now in `reciprocity.py`; two independent implementations agree).** Turn-taking@5min vs chance: `on_argmax` REAL 0.5% vs NULL 1.2%, **z −0.9 → AT/BELOW CHANCE** (1 dyad); `gemini_handonly` REAL 28.2% vs NULL 2.0%, **z +25.9 → ABOVE CHANCE** (6 dyads, top 35%); `claude_handonly` REAL 5.6% vs NULL 1.8%, **z +4.5 → above chance but ONE COUPLE** (3 dyads, top 82%). CONSEQUENCE: the banked project claim **"venture is the contact lever" rests on `on_argmax`, whose reciprocity is chance-level** — i.e. that "contact" was outwardness with no reciprocation in it. Real engagement is decoupled from / anti-correlated with moves+outwardness (most-moving claude_handonly bought least; least-moving gemini_handonly bought most) → it tracks **doula-mode/seed-model, not motion.** Open caveat: gemini's above-chance reciprocity survives the VOLUME null but maybe not a model-STYLE prior (gemini may just write turn-taking-shaped dialogue) — only same-seed ON-vs-OFF controls that.
3. **The casting decay-monoculture: seed model, or feedback loop?** RAW: the seed model (deepseek) on 10 fixed dealt-hands with NO world-context = 11–20% built-env/decay souls. The real deepseek-seeded running cast = **78%**. Injecting decay-world-facts into the same prompt drove deepseek 11%→100%; neutral-facts suppressed gemini 80%→40%. A one-line seed-cut (`WW_DOULA_HAND_ONLY`) produced a 13% cast in one run. UNTESTED across more than one run; the cold-start tip is unidentified.
4. **An unverified claim from inside the house:** a familiar (the Archivist) asserted that `openrouter-activity-20260606-090535.csv` shows API calls during a window that commit `cee66b1` logged as "dormant" — a contradiction. This has NOT been checked against the actual CSV and commit. Treat as unverified.

## Standing cautions (the project's own scars — they apply to YOU)
- **A metric measures what it COMPUTES, not what it is NAMED.** "CONTACT" computed outwardness. When a chapter cites a measured quantity, ask what the code actually computed, not what the sentence calls it.
- **Vivid single cases have been over-read into rates, repeatedly** (a felt-sense read as "engaged" when the ledger showed zero utterances; an early-population glance read as "healthy" that the ripe instrument called the opposite). Distrust any n=1 doing the work of a frequency.
- **Confident, specific-sounding output is not verified output** (see open question 4). A receipt that names a filename and a commit can still be a confabulation until someone opens both.

---
*Raw evidence and draft chapters get added here as they come. Keep the project's framing off this desk.*
