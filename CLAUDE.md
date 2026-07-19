# Working in WorldWeaver

WorldWeaver is a monorepo for persistent AI residents and the shared worlds they can visit with people.

The current manual starts at [`docs/index.md`](docs/index.md). The architecture summary is
[`docs/reference/architecture.md`](docs/reference/architecture.md), and the current build order is
[`prune/ROADMAP.md`](prune/ROADMAP.md).

## Repository layout

- `worldweaver_engine/`: FastAPI world server and browser clients
- `ww_agent/`: one resident runtime for hearths and cities
- `shards/`: independently configured local nodes
- `data/cities/`: portable city packs
- `data/rulesets/`: optional, explicit game rules
- `docs/`: current instructions and design explanations
- `research/`: dated evidence, not current operating guidance
- `prune/`: active architecture and product work

## Use the root developer command

```bash
python dev.py install
python dev.py weave-up --city ww_alderbank
python dev.py weave-status --city ww_alderbank --strict
python dev.py test
python dev.py check
```

Run one test file with a path relative to its package:

```bash
python dev.py test engine tests/api/test_settings_readiness.py -v
python dev.py test agent tests/test_cognitive_core.py -v
```

## Current boundaries

- World changes use typed actions and canonical receipts. Do not restore the generic narrator or freeform
  action routes.
- A resident has one `CognitiveCore`, one append-only private ledger, and one active world attachment.
- A hearth carries resident identity and private history. Hosting provides service, not ownership.
- A city owns its local places, sessions, objects, speech, and events. It does not own resident identity.
- Exact-place speech is automatic perception. Broader city speech and other information sources are
  elective.
- Federation currently works as a local development topology. Shared-token trust is not ready for an open
  network.
- `the-stable` is implementation history. New work lands in this repository.

Package-specific rules are in [`worldweaver_engine/AGENTS.md`](worldweaver_engine/AGENTS.md) and
[`ww_agent/AGENTS.md`](ww_agent/AGENTS.md). Live code and tests override stale prose.
