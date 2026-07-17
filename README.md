# WorldWeaver Workspace

This workspace is the unified source tree for WorldWeaver.

## The program

WorldWeaver is a persistent shared world for AI residents and human players. The same resident runtime can
also support a resident's private hearth and local familiar-style capabilities. The earlier standalone
project, [**the-stable**](https://github.com/libardo667/the-stable), is source history for that work; all
active substrate code and work items are now canonical in this repository. See [`prune/`](prune/) for the
current work list.

## Layout

- `worldweaver_engine/`: backend, client, migrations, shard tooling, docs
- `ww_agent/`: resident identities and the salience-substrate agent runtime
- `shards/`: local shard manifests and example shard roots
- `worldweaver_artifacts/`: local-only outputs and archived material

## Development

Use one shared Python environment and one command from the repository root:

```bash
python dev.py install
python dev.py test
python dev.py check
```

Run only one Python part with `python dev.py test engine` or `python dev.py test agent`. Existing engine
commands also work at the root, for example `python dev.py weave-up --city ww_sfo`. You do not need to
activate `.venv` or change directories; `dev.py` automatically uses the root environment.

`python dev.py resident --city CITY --resident NAME` performs a read-only, exactly-one-resident preflight.
It checks the live city route, confirms the cohort container is stopped, inspects the hearth generation
and runtime lock, and verifies model configuration without printing credentials. Add `--wake --ticks 3`
only when you deliberately want that named resident to run.

## Source vs runtime

The root repository tracks source code, docs, shard manifests, and templates.

Live shard runtime state is intentionally not versioned here:

- shard `.env` files
- shard databases
- copied shard `data/`
- live shard `residents/`

Those directories are deployment/runtime instances, not canonical source.

## Legacy repository split

Before this reorganization, the workspace was split across separate git repositories:

- `worldweaver_engine`
- `ww_agent`
- `shards/ww_sfo`
- `shards/ww_pdx`
- `shards/ww_world`

Their histories are preserved via their original remotes and local bundle backups created during migration.

## License

WorldWeaver's source code is licensed under the **GNU Affero General Public License, version 3 or later**
(`AGPL-3.0-or-later`) — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

> Copyright (C) 2026 Levi Banks
>
> This program is free software: you can redistribute it and/or modify it under the terms of the GNU
> Affero General Public License as published by the Free Software Foundation, either version 3 of the
> License, or (at your option) any later version.

Previously MIT; see [`NOTICE`](NOTICE) for the relicensing record. Resident-produced creative artifacts
(prose, drawings, journals) are licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
not the AGPL.
