def test_travel_destinations_endpoint_returns_discovery_without_moving_an_actor(
    client, monkeypatch
):
    expected = {
        "source": {"shard_id": "sf-community", "city_id": "san_francisco"},
        "registry": {"configured": True, "reachable": True},
        "destinations": [
            {
                "route_id": "sf-pdx",
                "to_city_id": "portland",
                "availability": "available",
                "nodes": [{"shard_id": "rose-city-coop"}],
            }
        ],
    }
    monkeypatch.setattr(
        "src.services.federation_discovery.get_travel_destinations",
        lambda: expected,
    )

    response = client.get("/api/world/travel/destinations")

    assert response.status_code == 200
    assert response.json() == expected
