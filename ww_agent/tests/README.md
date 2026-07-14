# Agent tests

Run the complete suite from `ww_agent/`:

```bash
.venv/bin/python -m pytest tests -q
```

The suite protects the current substrate: cognitive-core ordering, ledger/reducer behavior, salience
and prediction, pulse/action selection, identity and honest-briefing contracts, rest/circadian state,
incubation, growth proposals, familiar file scope, city sources, doula behavior, and substrate-sync
classification.

Prefer small deterministic tests at module seams. Add a regression test when changing an invariant,
route shape, ledger event, reducer, identity fact, or sync-manifest classification. Tests for deleted
loop-bank capability partitions or tiered-memory ownership should not be recreated.
