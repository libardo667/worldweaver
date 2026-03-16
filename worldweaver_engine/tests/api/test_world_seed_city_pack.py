from src.models import WorldEdge, WorldNode


def test_world_seed_defaults_to_deterministic_city_pack(client, db_session, monkeypatch):
    pack = {
        "neighborhoods": [
            {
                "id": "north-beach",
                "name": "North Beach",
                "region": "central",
                "vibe": "Cafe tables and steep walks toward the bay.",
                "adjacent_to": [],
                "lat": 37.8004,
                "lon": -122.4101,
            }
        ],
        "landmarks": [],
        "street_corridors": [],
        "transit_graph": {},
    }

    monkeypatch.setattr("src.services.city_pack_seeder.get_pack", lambda city_id: pack)

    def _unexpected_llm(*args, **kwargs):
        raise AssertionError("Default city-pack seeding should not call LLM enrichment")

    monkeypatch.setattr("src.services.city_pack_seeder.get_llm_client", _unexpected_llm)

    response = client.post(
        "/api/world/seed",
        json={
            "world_theme": "Test city life",
            "player_role": "resident",
            "description": "A deterministic default seed.",
            "tone": "grounded",
            "storylet_count": 5,
            "city_id": "testopolis",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["city_pack_used"] == "testopolis"
    assert body["nodes_seeded"] == 1


def test_world_seed_city_pack_fast_mode_skips_llm_and_writes_graph(client, db_session, monkeypatch):
    pack = {
        "neighborhoods": [
            {
                "id": "north-beach",
                "name": "North Beach",
                "region": "central",
                "vibe": "Cafe tables, old apartments, and a steady slope toward the water.",
                "adjacent_to": ["chinatown"],
                "lat": 37.8004,
                "lon": -122.4101,
            },
            {
                "id": "chinatown",
                "name": "Chinatown",
                "region": "central",
                "vibe": "Busy sidewalks, produce stands, and alleys full of deliveries.",
                "adjacent_to": ["north-beach"],
                "lat": 37.7941,
                "lon": -122.4078,
            },
        ],
        "landmarks": [
            {
                "id": "portsmouth-square",
                "name": "Portsmouth Square",
                "description": "A plaza with benches, chess tables, and constant foot traffic.",
                "type": "square",
                "neighborhood": "chinatown",
                "lat": 37.7949,
                "lon": -122.4056,
            }
        ],
        "street_corridors": [
            {
                "id": "grant-avenue",
                "name": "Grant Avenue",
                "type": "commercial",
                "neighborhoods": ["chinatown", "north-beach"],
                "vibe": "Shopfronts, hanging signs, and tourists mixing with deliveries.",
            }
        ],
        "transit_graph": {
            "muni": {
                "stations": [
                    {
                        "id": "chinatown-station",
                        "name": "Chinatown Station",
                        "system": "muni",
                        "neighborhood": "chinatown",
                        "notes": "Platform crowds and escalators humming under Stockton Street.",
                        "lines": ["T"],
                        "connects_to": [],
                        "lat": 37.7946,
                        "lon": -122.4072,
                    }
                ]
            }
        },
    }

    monkeypatch.setattr("src.services.city_pack_seeder.get_pack", lambda city_id: pack)

    def _unexpected_llm(*args, **kwargs):
        raise AssertionError("LLM enrichment should not run in fast city-pack mode")

    monkeypatch.setattr("src.services.city_pack_seeder.get_llm_client", _unexpected_llm)

    response = client.post(
        "/api/world/seed",
        json={
            "world_theme": "Test city life",
            "player_role": "resident",
            "description": "A small deterministic test world.",
            "tone": "grounded",
            "storylet_count": 5,
            "seed_from_city_pack": True,
            "enrich_city_pack": False,
            "city_id": "testopolis",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["city_pack_used"] == "testopolis"
    assert body["nodes_seeded"] == 5

    nodes = db_session.query(WorldNode).all()
    assert len(nodes) == 5
    assert any((node.metadata_json or {}).get("description") == pack["neighborhoods"][0]["vibe"] for node in nodes)
    assert any((node.metadata_json or {}).get("description") == pack["landmarks"][0]["description"] for node in nodes)

    edges = db_session.query(WorldEdge).all()
    assert edges
    assert any(edge.edge_type == "path" for edge in edges)
