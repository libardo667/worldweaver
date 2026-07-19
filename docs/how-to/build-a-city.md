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
shells before writing the pack. Its command-line layer only retrieves optional source data and writes the
result. Pack assembly, fictional-map compilation, and validation run through the same in-memory service that
the planned City Studio will use.

## Preview before habitation

After creating a shard, inspect:

```text
GET /api/shard/city-pack/preview
```

The preview works before the world is seeded. Fictional packs report a schematic map style and must not be
placed over real map tiles.

A generated fictional map is split into local sections. Each section records its own seed, revision, lock
state, and decorative details. Shared seam records—not either section—own river and path crossings plus the
terrain and region values along the border. Lock reviewed sections before export. The low-level section edit
helper exists now; the browser controls are still planned for City Studio.

## Work in a private draft

Create a validated draft without changing `data/cities` or a running shard:

```bash
python dev.py city-draft create --city alderbank
python dev.py city-draft inspect alderbank
python dev.py city-draft preview alderbank
```

Draft files live in the ignored, node-local `worldweaver_engine/data/city_drafts/` directory. The preview
command prints the full generated SVG path. You can also inspect or revise one map section:

```bash
python dev.py city-draft preview alderbank --section section-0-0
python dev.py city-draft section alderbank section-0-0 unlock
python dev.py city-draft section alderbank section-0-0 reroll
python dev.py city-draft section alderbank section-0-0 lock
```

A reroll is refused while the section is locked. Every successful edit rebuilds and validates the private
preview. These commands do not publish a pack; first publication remains a separate future operation.

For the same workflow in a browser, run:

```bash
python dev.py city-studio
```

City Studio opens on `127.0.0.1` and uses a fresh access token for that process. It is a separate local app,
not a route on the public shard server. The first screen can create a draft from a checked-in city
configuration, show the full generated map, focus any section, and unlock, reroll, or relock that section.
Stop it with Ctrl+C. Import, general place editing, export, and first publication are still future work.

## Create a local shard

```bash
python dev.py new-shard CITY_ID \
  --port 8005 \
  --federation http://localhost:9000 \
  --runtime-federation http://host.docker.internal:9000
```

The generated folder uses immutable engine and agent images for the current Git commit. It does not build or
mount either source tree. Review its `.env`, then operate it from that folder:

```bash
cd PATH_TO_GENERATED_NODE
python ww.py setup
python ww.py start
python ww.py seed
```

Do not add residents until the city has been reviewed and seeded. Residents remain stopped unless you later
run `python ww.py start --agents`.

## Do not rebuild an inhabited city in place

Seeding founds a world. Once people or residents have inhabited it, changing the underlying pack requires an
explicit migration plan. The current tools do not provide that migration. Treat an inhabited pack as
read-only.

An additive generated-map drawing is narrower than a city rebuild. On a city explicitly approved for map
experiments, inspect and publish a built drawing from inside its isolated node folder:

```bash
python ww.py map inspect /path/to/built-city-pack
python ww.py map publish /path/to/built-city-pack --yes
```

The publisher verifies the city, version, artifact hash, SVG hash, passive SVG content, and canonical route
set. It refuses any change to the node's actual neighborhood, landmark, path, travel, stoop, weather, or
transit files. It also refuses to run while resident agents are active, makes a full private backup, and
restarts the backend. This command does not authorize a general inhabited-city migration.

The planned City Studio will put the same builder and validator behind a steward-facing browser editor. It
will not introduce a second city format.
