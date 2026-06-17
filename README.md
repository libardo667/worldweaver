# WorldWeaver Workspace

This workspace is the unified source tree for WorldWeaver.

## The program and its pilots

WorldWeaver is the whole made thing: a persistent, mixed-intelligence world its residents live in. It runs
the same cognitive substrate at city scale that its **pilot**, [**the-stable**](https://github.com/libardo667/the-stable),
runs as a clean single-machine fractal sample — local AI *familiars* you tend, the mechanism zoomed in for
inspection. **the-mews** is a sibling embodiment. The work-item discipline they all run on is extracted as a
reusable kit, [**prune**](https://github.com/libardo667/prune).

Work items are stored by subject: the cognitive substrate (`prune/` majors 49–59) is **canonical in
the-stable**; this repo runs it and keeps pointer stubs. See [`prune/`](prune/).

## Layout

- `worldweaver_engine/`: backend, client, migrations, shard tooling, docs
- `ww_agent/`: agent runtime, resident templates, agent loops
- `shards/`: local shard manifests and example shard roots
- `worldweaver_artifacts/`: local-only outputs and archived material

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
