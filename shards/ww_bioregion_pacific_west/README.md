# ww_bioregion_pacific_west

**Status: Stub — not yet seeded or running**

Bioregion-level shard covering the Pacific West coast.

## Logical children (city shards)
- `ww_sfo` — San Francisco, CA
- `ww_pdx` — Portland, OR
- `ww_seattle` — Seattle, WA (future)

## Planned fact graph scope
- Climate patterns and seasonal weather corridors
- Migration routes (human and wildlife)
- Regional transit networks (Amtrak Cascades, Coast Starlight)
- Bioregional landmarks and geography

## When this shard activates
When inter-city travel (Major 07) is implemented, city shards will pulse
to this bioregion shard rather than directly to ww_world. The bioregion
aggregates residents across its cities and exposes regional context to agents.

## To bootstrap
```bash
python worldweaver_engine/scripts/new_shard.py pacific_west \
    --type bioregion --port 8010 \
    --federation http://ww_world:9000 \
    --token <token>
```
