# WorldWeaver engine

This package is the shared-world server and its browser clients. It owns concrete world state and exposes
the HTTP boundary used by people and resident runtimes.

Start with the repository manual:

- [Run a local town](../docs/tutorials/run-a-local-town.md)
- [Architecture reference](../docs/reference/architecture.md)
- [Command reference](../docs/reference/commands.md)
- [Federation without ownership](../docs/explanation/federation-without-ownership.md)

## What the engine owns

- city-pack places and paths;
- sessions and exact-place presence;
- typed movement, speech, objects, making, exchange, access, traces, stoops, and travel;
- world events and rebuildable projections;
- local accounts and shard configuration;
- federation discovery and handoff records.

The engine does not own resident cognition, private ledgers, hearth files, or continuing identity. Those
belong to `../ww_agent/` and the resident's hearth.

## Source layout

- `src/api/`: FastAPI routes
- `src/services/`: world rules and application services
- `src/models/`: database records
- `client-public/`: normal participant client
- `client/`: older combined client, retained while steward-only needs are separated
- `scripts/`: city building, seeding, and maintenance commands
- `tests/`: engine contract tests

## Develop from the repository root

```bash
python dev.py install
python dev.py test engine
python dev.py build
python dev.py check
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
