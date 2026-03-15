# Legacy Repository Boundaries

This workspace was consolidated into a single root repository on 2026-03-15.

The pre-consolidation repository heads at migration time were:

- `worldweaver_engine`
  - remote: `https://github.com/libardo667/worldweaver_engine.git`
  - branch: `main`
  - head: `7617ec1bc9c76ef87d9cc0d4fbac54696a37a050`
- `ww_agent`
  - remote: `https://github.com/libardo667/ww_agent.git`
  - branch: `main`
  - head: `3994c2e4f6a41e605603909b80fe14a40ccdd3b2`
- `shards/ww_sfo`
  - local repo
  - head: `53a0240691435a591d5b43592bc2de1935c226f1`
- `shards/ww_pdx`
  - local repo
  - head: `f90bb01341bb0a4900f6544fae7791ef32446a2c`
- `shards/ww_world`
  - local repo
  - head: `480f30fbf559710793f1e81c3fc389d8eaad773a`

Local bundle backups were created before removing nested `.git` directories.
