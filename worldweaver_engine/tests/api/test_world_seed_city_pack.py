from pathlib import Path

from src.config import settings
from src.models import MaterialPool, WorldEdge, WorldNode, WorldStoop


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

    monkeypatch.setattr("src.services.llm_client.get_llm_client", _unexpected_llm)

    response = client.post(
        "/api/world/seed",
        json={
            "world_theme": "Test city life",
            "player_role": "resident",
            "description": "A deterministic default seed.",
            "tone": "grounded",
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

    monkeypatch.setattr("src.services.llm_client.get_llm_client", _unexpected_llm)

    response = client.post(
        "/api/world/seed",
        json={
            "world_theme": "Test city life",
            "player_role": "resident",
            "description": "A small deterministic test world.",
            "tone": "grounded",
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


def test_opted_in_game_pack_founds_validated_stoop_fixture(client, db_session, monkeypatch):
    rules = Path(__file__).resolve().parents[2] / "data" / "rulesets" / "private_constructive_game.v1.example.json"
    monkeypatch.setattr(settings, "shard_experience_path", str(rules))
    monkeypatch.setattr(settings, "shard_id", "test-game-shard")
    pack = {
        "neighborhoods": [
            {
                "id": "commons-bank",
                "name": "Commons Bank",
                "region": "center",
                "vibe": "A compact village center.",
                "adjacent_to": [],
                "lat": 45.014,
                "lon": -122.001,
            }
        ],
        "landmarks": [
            {
                "id": "alderbank-commons",
                "name": "Alderbank Commons",
                "description": "The village green.",
                "type": "public_square",
                "neighborhood": "commons-bank",
                "lat": 45.014,
                "lon": -122.001,
            }
        ],
        "street_corridors": [],
        "transit_graph": {},
        "stoops": [
            {
                "stoop_id": "alderbank-commons-stoop",
                "title": "The Commons Stoop",
                "prompt": "Leave one real thing for whoever comes next.",
                "location": "Alderbank Commons",
                "capacity": 8,
            }
        ],
    }
    monkeypatch.setattr("src.services.city_pack_seeder.get_pack", lambda city_id: pack)

    response = client.post(
        "/api/world/seed",
        json={
            "world_theme": "A small fictional river village",
            "player_role": "resident",
            "description": "A deterministic game-town seed.",
            "tone": "ordinary",
            "seed_from_city_pack": True,
            "enrich_city_pack": False,
            "city_id": "alderbank",
        },
    )

    assert response.status_code == 200, response.text
    stoop = db_session.get(WorldStoop, "alderbank-commons-stoop")
    assert stoop is not None
    assert stoop.location == "Alderbank Commons"
    assert stoop.capacity == 8
    assert db_session.query(MaterialPool).count() == 2
    assert {row.location for row in db_session.query(MaterialPool).all()} == {"Alderbank Workshop"}
