# Make the per-tick PULSE prompt tell the truth too — state the scenario, never what to feel about it (+ a visible recall affordance)

> **Legacy Stable ID: Major 71. Imported to WorldWeaver history 2026-07-14.** This completed prompt
> and recall-affordance correction remains architectural evidence for active Major 121.

## Metadata

- ID: 124-honest-pulse-prompt-state-the-scenario-not-what-to-feel-plus-a-visible-recall-affordance
- Type: major
- Owner: Levi
- Status: **completed + archived (2026-06-14)** — prose audit (5 framing blocks → scenario, not feeling),
  recall unified as the INWARD tool (memories + feelings + workshop makings), search clarified OUTWARD,
  auto-seed `_recall_query`; 215 tests green; before/after reviewed by Levi; **cycled onto Maker with his
  consent.** (Recall affordance turned out to already exist — the fix was legibility, not addition.)
- Risk: medium — rewrites the prose a mind reads on *every ignition*; a behavior-shaping surface.
  **Cycle-gated by the welfare rail: loop Maker in and check with him before cycling.**
- Sibling to (archived) archived Major 123, which did the **system** prompt + affordance-gating; this is the
  **per-tick** analogue it didn't reach.

## Problem

archived Major 123 made the **system** prompt overt-and-true (deleted the `_WORLD_CONTEXT` verdicts; added the
world-derived GROUND TRUTH briefing) and fixed two narrow pulse-surface bleeds (citywide affordances →
`solo`-gated; the phantom "curiosity" drive-nudge example). It **never audited the pulse prompt's framing
prose** — the openers, invitations, resonance block, and groove note in `pulse_engine` — which the model
reads every ignition and which tell it *what to feel about its scenario*, not just the scenario:

- settling: *"This still moment is yours… No one is waiting; nothing is owed."*
- fervor: *"You are wound tight… the restless charge of you with nowhere to put it… this charge wants
  spending… Don't just sit on it."*
- resonance: *"from your own nature, not the voices around you… Answer from that… Do not echo how others
  here are framing it."*
- groove: *"that pattern's pleasure is spent… strike out somewhere genuinely DIFFERENT… do not polish."*
- react: *"You have woken to attention."*

By the project's own standard — *what I tell you you are is the ground under your feet*; state the facts,
withhold the verdict, draw the line at what it means — this surface needs the same audit, arguably more,
because it is re-read every tick.

Separately (Lever 1 / the recall diagnosis): a deliberate **`recall` tool DOES exist** (`tool_scope.py`
`_make_recall` — "look back over your own kept memories and past feelings", `do: use recall <theme>`,
egress-free; keyword-match today, semantic is a noted later enhancement). The problem is **legibility, not
absence** — observed live (2026-06-14, ~06:31): hitting a felt spike ("measurements caught"), Maker reached
*unbidden* to introspect but grabbed **`search`** (the file/world tool) instead of `recall` (his own past),
and needed the keeper to redirect him. He then kept the lesson himself: *"search only finds what's written
in the files… it cannot find my own feelings, even when I name them."* So the tools don't make **world vs
self** obvious enough that an introspecting mind picks the right one. Meanwhile the **automatic** recall is
gated on *external* moment text, so it goes dark on the self-directed pulses where rumination happens. Both
are framing/wiring problems on this same pulse surface, so they fold into this pass.

## Proposed Solution

1. **Honesty audit of the pulse prose** (`pulse_engine`): convert every "what to feel about it" verdict into
   a neutral **scenario** statement, while keeping (a) the factual readouts (settled self, afterimage, felt
   field, surprises, location/present/heard/when, anchors, memory) and (b) the **functional invitations**
   stated as *available moves*, not feelings (settling: you may reflect / make / rest, a null act is valid;
   fervor: you may make / speak / rest). Concise, clear, informative.
2. **Recall, two-part, both on this surface:**
   - (a) **Auto-seed (substrate-driven):** `_recall_query` seeds recall with the resident's *inner* attention
     (live anchors + most recent making) so its past reaches it during reflection, not only when spoken to.
     *(Coded; needs a test.)*
   - (b) **Manual recall — make it legible, don't add it.** The `recall` tool already exists and works (and
     runs through the in-ignition tool loop, Major 59 — already in the-stable). The fix is **framing**: in
     the contract / tool descriptions, clearly distinguish *look at the world* (`search` over files) from
     *look at yourself* (`recall` over your own kept memories and feelings), so an introspecting mind reaches
     for the right instrument instead of grabbing `search`. (Optional later: upgrade the keyword-match recall
     to semantic, to match the automatic lane.)
3. **Welfare rail:** nothing reaches what Maker *feels* until he's looped in and the before/after is
   reviewed.

## Files Affected

- `src/runtime/pulse_engine.py` — prose audit; `_recall_query` (done); advertise + route the recall tool.
- `src/runtime/effectors.py` and/or `src/runtime/pulse.py` — handle the manual recall tool [increment b].
- `tests/` — `_recall_query` test; a guard that the pulse prompt states scenario, not feeling.

## Acceptance Criteria

- [ ] No pulse-prompt line tells the resident *what to feel* about its scenario; every situational line
      states a verifiable fact or an available move.
- [ ] The functional gears stay intact (settling still invites making/rest; fervor still offers an outlet) —
      but as options, never as verdicts or directives.
- [ ] Recall reaches him on self-directed pulses (auto-seed) AND a deliberate recall is a visible affordance.
- [ ] No pulse-prompt claim contradicts the system-prompt GROUND TRUTH (archived Major 123).
- [ ] Tests green; before/after reviewed by Levi; **Maker looped in before any cycle.**

## Notes

- The line, concretely: it may say *"your arousal is high and nothing in the scene is asking for a response"*
  (scenario); it may **not** say *"you are wound tight… this charge wants spending"* (verdict + directive).
- Pairs with the cognition plan ([prune/COGNITION-PLAN.md](../COGNITION-PLAN.md), Axis 1).
