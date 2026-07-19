---
title: Build and validate a city
sidebar_position: 2
---

# Build and validate a city

A city pack describes a place. A shard is one independently operated server hosting that pack. They have
different identities.

## Add a city configuration

City build configurations live in:

```text
worldweaver_engine/scripts/city_configs/
```

Real cities may include curated data and optional OpenStreetMap enrichment. A fictional city must declare
itself fictional and state the source and license for its authored material.

## Build one pack

```bash
python dev.py run worldweaver_engine/scripts/build_city_pack.py --city CITY_ID
```

For a repeatable build without network enrichment:

```bash
python dev.py run worldweaver_engine/scripts/build_city_pack.py --city CITY_ID --offline
```

The builder validates identifiers, coordinates, adjacency, paths, travel hubs, entry points, and stoop
shells before writing the pack.

## Preview before habitation

After creating a shard, inspect:

```text
GET /api/shard/city-pack/preview
```

The preview works before the world is seeded. Fictional packs report a schematic map style and must not be
placed over real map tiles.

## Create a local shard

```bash
python dev.py run worldweaver_engine/scripts/new_shard.py CITY_ID \
  --port 8005 \
  --federation http://localhost:9000 \
  --runtime-federation http://ww_world-backend:8000
```

Review the generated `.env` and compose file before starting it.

## Do not rebuild an inhabited city in place

Seeding founds a world. Once people or residents have inhabited it, changing the underlying pack requires an
explicit migration plan. The current tools do not provide that migration. Treat an inhabited pack as
read-only.

The planned City Studio will put the same builder and validator behind a steward-facing browser editor. It
will not introduce a second city format.
