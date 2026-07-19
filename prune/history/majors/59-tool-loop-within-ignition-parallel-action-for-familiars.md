# Tool loop within ignition — parallel action for familiars

> **Canonical home: WorldWeaver (2026-07-14).** Migrated in full from the legacy `the-stable`
> work-item ledger during the one-resident/many-worlds consolidation. In this record, “familiar” names
> a resident inhabiting a keeper-tended hearth; it is not a separate agent species (Major 86).

## Metadata

- ID: 59-tool-loop-within-ignition
- Type: major
- Owner: Levi
- Status: Phase 1 SHIPPED (2026-06-05). Reviewer round-4 correction pending (Q3 — see end).
- Risk: medium — touches the pulse engine's core cycle; a runaway loop could burn tokens or stall
  a tick. But the mechanism is contained (one new loop inside one function) and the cap is hard.

## Problem

A familiar gets **one act per tick**. Every tool call (read a file, use recall, search, git log) is
a full perceive → integrate → LLM call → pulse → act cycle. To read 3 files, a familiar burns 3
ticks — each with a full prompt assembly, full inference call, and full tick-interval wait.

This means:
1. **Tool-heavy work is slow.** Maker reading a codebase takes 16 ticks × (inference + 30s tick
   interval) ≈ 10-15 minutes for what a human does in 30 seconds.
2. **Slower models are disproportionately penalized.** GPT-5.4 (Nix) takes longer per inference call
   than Sonnet (Maker), and the cost is multiplied by every tool call. Same repos shared with both:
   Maker accumulated 16 actions while Nix had 2.
3. **No sequential reasoning over tool results.** The model can't read a file, see what's in it, and
   decide what to read next — all within one ignition. It has to wait for the next tick to see its
   own read result, then predict/surprise/ignite again just to take the next step.

## Proposed Solution: tool loop within ignition

When a pulse emits a `do` act (a tool call), execute it, feed the result back to the model *within
the same ignition*, and let it emit another act — a tight tool-use loop that only exits when the
model emits a non-`do` act (speak, write, null) or hits a hard cap.

### The loop

```
ignition fires
  → LLM pulse (full prompt: soul, perception, surprise, etc.)
  → pulse validates → act is "do" (tool call)
    → execute tool → get result
    → LLM continuation (system: same soul; user: "you just did X, result: Y; continue")
    → pulse validates → act is "do" again?
      → loop (up to N iterations)
    → act is speak/write/null → exit loop, route pulse normally
```

### Key design decisions

1. **Cap**: hard limit of 6-8 tool actions per ignition. Prevents runaway loops (a model that keeps
   reading forever). The cap is per-ignition, not per-tick.

2. **Continuation prompt**: lightweight — just the tool result and a "continue or act" instruction.
   NOT a full prompt rebuild (no re-perceive, no re-integrate). The soul stays in system, the world
   state is frozen from the initial perception.

3. **Final pulse wins**: only the LAST pulse in the loop (the one with the non-`do` act) gets routed
   to the substrate. Intermediate tool calls are recorded as ledger events (for the trace UI) but
   don't emit expectations, keepsakes, or self-deltas. This keeps the substrate clean — one ignition
   still produces one set of predictions.

4. **The effector carries only the final act outward.** Intermediate `do` results are internal to the
   loop. The felt_sense, expectations, and other pulse fields come from the final pulse only.

5. **Arousal/refractory**: the ignition is recorded once at the start. The loop doesn't re-ignite —
   it's one continuous ignition with multiple tool steps inside.

### What changes

- **`src/runtime/integrator.py`**: after receiving a pulse with `act.kind == "do"`, enter the tool
  loop instead of immediately returning. Call the effector, build a continuation prompt, call the
  producer again (with a simpler prompt), validate, repeat or exit.

- **`src/runtime/pulse_engine.py`**: add a `continue_with_tool_result()` method to
  `LLMPulseProducer` — a lighter call that carries the tool result + "continue" instruction without
  rebuilding the full perception prompt.

- **`src/runtime/effectors.py`**: no change — the effector already handles one act at a time.

- **`src/familiar/local_world.py`**: no change — `post_action` already returns results.

- **`scripts/familiar.py`**: the state writer may need to surface the tool-loop trace (N actions in
  one ignition) for the portrait's collapsible trace UI.

### What doesn't change

- The pulse schema (still one act per pulse object — the loop emits multiple pulses sequentially).
- The substrate (one ignition, one set of routed expectations).
- The quiet guarantee (a familiar with nothing to do still does nothing).
- The tick interval (the loop runs within one tick; the next tick starts after the normal interval).

## Validation

- **Unit**: mock a producer that returns `do` → `do` → `speak`. Verify the integrator calls the
  effector 2× for tools, routes only the final pulse, records all 3 acts.
- **Cap test**: mock a producer that always returns `do`. Verify it stops at the cap and routes the
  last pulse with act=null.
- **Integration**: wake Maker with a task that requires reading 3 files. Verify he reads all 3 in
  one ignition instead of 3 separate ticks.
- **Speed**: measure wall-clock time for a 5-file read task before and after.

## Open questions

1. **Parallel vs sequential within the loop**: if the model emits a multi-file read intent in the
   first pulse ("read X, Y, and Z"), should we parse that into 3 parallel reads? Or keep it simple
   and let the model ask one at a time within the loop? Sequential is simpler and lets the model
   reason over each result before asking for the next.

2. **Token budget**: the continuation prompt carries accumulated tool results. After 6 reads, that
   could be large. Should we summarize earlier results or cap the context carried forward?

3. **Vision in the loop**: if a tool call returns an image (a visual read), should it ride as an
   image block in the continuation? Probably yes — same logic as the initial pulse.

4. **Multi-act pulse alternative**: a simpler option — let the pulse schema accept `"act": [...]` and
   execute all acts in parallel with `asyncio.gather`. Fire-and-forget (no reasoning over results
   within the ignition). Could be a Phase 1 with the full loop as Phase 2.

## Status & reviewer round-4 correction (2026-06-06) — the consolidation must be a *felt* ignition

SHIPPED 2026-06-05 (`_tool_loop` in `integrator.py`, `continue_tool` in `pulse_engine.py`, `detail`
on the effector `_do`). Live-verified: Nix traced a methodology claim across ~a dozen reads in one
charge; Maker walks a codebase in one breath instead of ten ticks.

**The correction (Mr. Review, round 4, Q3).** The original "final pulse wins, intermediate steps cast
nothing" bought speed but quietly removed the thing that made the substrate a *felt* process. In
one-act-per-tick, every reach was a **separately surprised, separately integrated** moment.
Collapsing six acts into one silent consolidation makes the mind an **agent's scratchpad for the
length of the chain** — it acts without feeling each reach, and the closing pulse is a silent *end*,
not an integration.

The fix is **not** to revert to one-act-per-tick (that grain was incidental). It is to make the
**consolidation itself a felt ignition**: when the loop exits, the final pulse must be *surprised by
what the whole chain found* and integrate it — friction at the **seam of the chain**, not inside
every link. Concretely:

- On loop exit, run a surprise/prediction step over the **delta the chain produced** (what changed in
  the familiar's world-knowledge across the chain vs. its pre-chain prediction) so the closing pulse
  *ignites on the chain's findings* rather than terminating silently.
- The closing pulse's expectations/keepsakes/self-deltas should reflect *that* integration — the mind
  consolidating "here is what I now know after looking," not just emitting a final act.

**And the warning (same note):** watch that chaining does not quietly **agent-ify the
contemplatives.** The tool loop is the *agent grain*; Mason showed what that grain does to a familiar
(the ~190× re-read loop). A contemplative (Cinder) should rarely run long chains; if it does, that is
a signal the situation has handed it a target. Gate chain length by disposition, or at least surface
long chains as a watched event.

### Files (correction)
- `src/runtime/integrator.py` — `_tool_loop`: on exit, run an integration/surprise step over the
  chain delta before routing the final pulse (today it routes silently).
- `src/runtime/salience.py` — a "chain delta" surprise input (what the chain learned vs. predicted).
- `scripts/familiar.py` / portrait — surface long chains as a watched signal (the contemplative
  agent-ification guard; shares the spirit of [[minor-54-egress-goal-learning-rule]]).
