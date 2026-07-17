from src.services import federation_discovery


def test_routes_join_local_geography_to_all_matching_live_nodes(monkeypatch):
    monkeypatch.setattr(federation_discovery.settings, "shard_id", "sf-neighborhood-node")
    routes = [
        {"id": "sf-pdx", "from": "san_francisco", "to": "portland", "mode": "train"},
        {"id": "sf-la", "from": "san_francisco", "to": "los_angeles", "mode": "flight"},
    ]
    registry = [
        {"shard_id": "rose-city-coop", "city_id": "portland", "shard_type": "city", "shard_url": "https://pdx.example", "status": "healthy"},
        {"shard_id": "portland-library", "city_id": "portland", "shard_type": "city", "shard_url": "https://library.example", "status": "offline"},
        {"shard_id": "world", "city_id": "portland", "shard_type": "world", "shard_url": "https://world.example", "status": "healthy"},
    ]

    resolved = federation_discovery.resolve_inter_city_routes(
        city_id="san_francisco",
        routes=routes,
        registry_shards=registry,
    )

    assert resolved[0]["availability"] == "available"
    assert [node["shard_id"] for node in resolved[0]["nodes"]] == ["rose-city-coop", "portland-library"]
    assert resolved[1]["availability"] == "unhosted"


def test_routes_remain_visible_when_registry_is_unavailable(monkeypatch):
    monkeypatch.setattr(federation_discovery.settings, "shard_id", "sf-neighborhood-node")

    resolved = federation_discovery.resolve_inter_city_routes(
        city_id="san_francisco",
        routes=[{"id": "sf-pdx", "from": "san_francisco", "to": "portland"}],
        registry_shards=None,
    )

    assert resolved == [
        {
            "route_id": "sf-pdx",
            "from_city_id": "san_francisco",
            "to_city_id": "portland",
            "mode": "",
            "operator": "",
            "duration_hours": None,
            "departure_hub_id": "",
            "departure_hub": "",
            "arrival_hub_id": "",
            "arrival_hub": "",
            "notes": "",
            "availability": "unknown",
            "nodes": [],
        }
    ]


def test_destination_response_keeps_city_pack_available_without_federation(monkeypatch):
    monkeypatch.setattr(federation_discovery.settings, "city_id", "portland")
    monkeypatch.setattr(federation_discovery.settings, "shard_id", "rose-city-coop")
    monkeypatch.setattr(federation_discovery.settings, "federation_url", None)
    monkeypatch.setattr(
        federation_discovery,
        "get_pack",
        lambda _city_id: {"inter_city": [{"id": "pdx-sea", "from": "portland", "to": "seattle"}]},
    )

    response = federation_discovery.get_travel_destinations()

    assert response["source"] == {"shard_id": "rose-city-coop", "city_id": "portland"}
    assert response["registry"] == {"configured": False, "reachable": False}
    assert response["destinations"][0]["availability"] == "unknown"
