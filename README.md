# WorldWeaver Workspace

This workspace is the unified source tree for WorldWeaver.

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
