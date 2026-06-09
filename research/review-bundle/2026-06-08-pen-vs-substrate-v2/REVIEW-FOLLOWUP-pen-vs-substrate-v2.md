# Mr. Review — second pre-mortem: "Pen vs Substrate" v2

This round asks you to pre-mortem a **revised** pre-registration (`DRAFT-preregistration-pen-vs-
substrate-v2.md`) before it locks and before any compute is spent. v2 is self-contained — you should
not need outside context. The method you hold yourself to is in `STANDING-BRIEF.md` (included here so
this bundle is a complete cold-start kit). Verify the empirical claims by recompute against
`research/runs/`; do not inherit them.

## The question in one line
The runtime LLM ("the pen") is already known to own a resident's *surface* (theme, register). The
project claims the pen does **not** own the *deep self* (its memories, its relationships) — those are
said to live in durable state, with the LLM "a swappable pen." We test that by swapping the LLM under
a developed resident and measuring whether memory + relationships survive while only style shifts.

## What changed from v1 → v2 (the first pre-mortem drove all of it)
The first pre-mortem predicted v1 would produce an **uninterpretable primary split** and found the
design leaked at four joints. v2's changes, each mapped to the finding:

1. **Free-run → frozen-instant probe.** The decisive catch: a free-running A/B is a closed feedback
   loop, so the two arms drift into different rooms and the primaries get measured against divergent
   opportunity sets (worse the longer it runs). v2 interrogates each resident at the fork with an
   **offline, byte-identical stimulus**, holding the opportunity set exactly constant. (§4.2)
2. **Memory metric: retrieved, not echoed.** v1's memory metric couldn't tell a surviving self from a
   pen quoting names sitting in its prompt. v2 scores only entities the substrate's relevance search
   surfaced (`recalled`) that are **absent from the live conversation** (`heard`), plus a
   suppression-ablation to kill confabulation. (§5 PRIMARY 2)
3. **Relationship metric: known-vs-stranger contrast.** v1's relationship metric was confounded with
   the pen's general talkativeness (which *is* surface). v2 has the same pen answer both an
   established partner and a stranger; only the **difference** counts, neutralizing disposition. (§5
   PRIMARY 1)
4. **Capability gate hardened + replication made mandatory.** Floor is now on **person-addressed**
   volume specifically (not total), and **≥2 pen-pairs are required** — because capability and self
   are not orthogonal (the pen is the self's only output channel), so a single-pen collapse cannot be
   read as "the self was the pen." (§5 capability floor, §7, §8.3)
5. **Verdict gains a pre-committed PARTIAL branch.** The predicted split (memory persists,
   relationships move) is now its own labelled outcome, so a split can't be read as whichever side is
   convenient. (§7)
6. **Individuation floor moved to substrate axes.** "Is there a self to lose" is checked on distinct
   memories/relationships/drives — not on surface, which is known to converge and to sit below the
   surface instruments' resolution. (§6)

## What I most want you to break
1. **Predict the §7 branch** before the run.
2. **PRIMARY 1** — can the known/stranger contrast still be gamed (e.g. a pen that name-drops *any*
   provided interlocutor equally)? 
3. **PRIMARY 2** — can a pen confabulate *around* the retrieved block in a way the suppression
   ablation won't catch?
4. **The probe itself** — is interrogating a frozen instant a fair stand-in for a live pulse, or does
   it quietly change the construct? If it does, what would you measure instead that still kills the
   trajectory confound?
5. **The seventh guard** §8 doesn't have.

If you predict a null/collapse and we build the protocol to be able to falsify you, that's the deal
again.
