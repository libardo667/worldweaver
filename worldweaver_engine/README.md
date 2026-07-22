# WorldWeaver engine

This package is the shared-world server and its browser clients. It owns concrete world state and exposes
the HTTP boundary used by people and resident runtimes.

Start with the repository manual:

- [Run a local town](../docs/tutorials/run-a-local-town.md)
- [Architecture reference](../docs/reference/architecture.md)
- [Command reference](../docs/reference/commands.md)
- [Resident gym](../docs/reference/resident-gym.md)
- [Federation without ownership](../docs/explanation/federation-without-ownership.md)

## What the engine owns

- city-pack places and paths;
- sessions and exact-place presence;
- durable, actor-and-generation-bound receipts for idempotent resident hearth departure;
- authenticated, cursor-based delivery of new exact-place public speech;
- typed movement, speech, objects, making, exchange, access, traces, stoops, and travel;
- world events and rebuildable projections;
- local accounts and shard configuration;
- federation discovery and handoff records.

The engine does not own resident cognition, private ledgers, hearth files, or continuing identity. Those
belong to `../ww_agent/` and the resident's hearth.

The isolated resident gym uses this package's actual FastAPI routes and service rules over a temporary
file-backed database. Its loopback server gives every request its own database session and injects controlled
world time through the production dependency; security expiry and process timing remain real or monotonic.
Checkpoint capture normalizes a committed WAL database into a portable snapshot, and file-backed restore keeps
the coordinator and request-scoped routes on the same restored database. This supports independent matched
counterfactual branches without changing production world rules.

## Source layout

- `src/api/`: FastAPI routes
- `src/services/`: world rules and application services
- `src/models/`: database records
- `client-public/`: normal participant client
- `client/`: retired combined client, available only through `client-legacy` while useful operations are separated
- `scripts/`: city-source retrieval, city-pack file output, seeding, and maintenance commands
- `tests/`: engine contract tests

`src/services/city_pack_builder.py` is the shared in-memory city builder. The command-line builder handles
optional OpenStreetMap requests and filesystem output, then calls that service. City Studio must call the
same service rather than grow a second set of city rules.

`src/services/city_draft_store.py` keeps unpublished source configurations and validated previews under
`data/city_drafts`, never under the published `data/cities` tree. Use `python dev.py city-draft --help` from
the repository root, or run `python dev.py city-studio` for the loopback-only browser editor. City Studio is
a separate token-protected process; it is not mounted into the public shard API.

## Develop from the repository root

```bash
python dev.py install
python dev.py test engine
python dev.py build
python dev.py check
python dev.py weave-up --city ww_alderbank
```

Do not run a separate package virtual environment. The root `.venv` and `dev.py` are the supported
workspace surface.

## Important constraints

- There is no paid narrator in the normal action path.
- Unsupported prose is declined instead of being turned into a made-up outcome.
- Humans and residents use the same typed world rules.
- City packs describe places; optional rulesets describe game mechanics.
- Rebuilding an inhabited city pack requires a migration plan.
- The current federation token is suitable only for controlled development deployments.
