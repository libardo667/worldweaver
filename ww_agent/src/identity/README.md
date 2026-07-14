# Identity

`loader.py` loads a resident's durable identity, compatibility tuning, and world-supplied situational
facts. It renders only facts the world reports; missing affordances stay silent rather than becoming
prompt folklore.

The identity seam distinguishes immutable canonical soul text from separately recorded growth. Runtime
cognition may propose growth, but it does not rewrite canon in place. See `runtime/growth_proposals.py`
and the identity tests for the maturation contract.

`LoopTuning` and loop-shaped keys in `tuning.json` remain compatibility inputs for existing resident
directories. Current consumers translate those values into pulse, rest, incubation, grounding, and
other substrate behavior. They are not evidence that the removed loop bank still exists.

When adding a situational affordance, update all three pinned surfaces together:

- `BRIEFING_FACT_KEYS` and its gated renderer line;
- the runtime world protocol documentation;
- the drift-catcher tests.

Never infer a claim about a resident's selfhood from deployment facts. State the circumstance and leave
its meaning open.
