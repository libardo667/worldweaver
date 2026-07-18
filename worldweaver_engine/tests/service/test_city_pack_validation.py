from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_city_pack import build_pack
from src.services import city_pack_service
from src.services.city_pack_validation import require_valid_city_pack, validate_city_pack


def test_published_city_packs_have_valid_local_travel_hubs():
    for city_id, expected_hub in (
        ("san_francisco", "emeryville-sf-transfer"),
        ("portland", "portland-union-station"),
        ("alderbank", "alderbank-footbridge"),
    ):
        city_pack_service._PACK_CACHE.pop(city_id, None)
        pack = city_pack_service.get_pack(city_id)

        assert pack is not None
        report = validate_city_pack(pack)
        assert report.valid, report.to_dict()
        assert city_pack_service.find_travel_hub(expected_hub, city_id) is not None


def test_validation_returns_structured_broken_reference_errors():
    report = validate_city_pack(
        {
            "manifest": {"city_id": "test_city", "schema_version": "1.1.0", "version": "0.1.0"},
            "neighborhoods": [
                {
                    "id": "center",
                    "name": "Center",
                    "lat": 45.0,
                    "lon": -122.0,
                    "adjacent_to": ["missing-place"],
                }
            ],
            "travel_hubs": [
                {
                    "id": "central-station",
                    "name": "Central Station",
                    "entry_location": "missing-place",
                    "modes": ["train"],
                }
            ],
            "inter_city": [
                {
                    "id": "test-away",
                    "from": "test_city",
                    "to": "away",
                    "departure_hub_id": "missing-hub",
                }
            ],
        }
    )

    assert report.valid is False
    assert {issue.code for issue in report.errors} == {
        "missing_arrival_hub_id",
        "unknown_departure_hub",
        "unknown_entry_location",
        "unknown_neighborhood",
    }
    payload = report.to_dict()
    assert payload["valid"] is False
    assert all(set(issue) == {"level", "code", "path", "message"} for issue in payload["errors"])


def test_require_valid_city_pack_raises_with_human_readable_paths():
    with pytest.raises(ValueError, match=r"manifest\.city_id"):
        require_valid_city_pack({"manifest": {}, "neighborhoods": []})


def test_offline_builder_uses_the_same_validator_and_writes_travel_hubs(tmp_path):
    engine_root = Path(__file__).resolve().parents[2]
    config = engine_root / "scripts" / "city_configs" / "portland.json"
    output = tmp_path / "portland"

    build_pack(config, output, offline=True)

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    hubs = json.loads((output / "travel_hubs.json").read_text(encoding="utf-8"))
    routes = json.loads((output / "inter_city.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.1.0"
    assert manifest["counts"]["travel_hubs"] == 1
    assert hubs[0]["entry_location"] == "pearl-district"
    assert routes[1]["arrival_hub_id"] == "emeryville-sf-transfer"


def test_fictional_builder_skips_osm_and_keeps_explicit_small_town_paths(tmp_path, monkeypatch):
    engine_root = Path(__file__).resolve().parents[2]
    config = engine_root / "scripts" / "city_configs" / "alderbank.json"
    output = tmp_path / "alderbank"

    monkeypatch.setattr(
        "scripts.build_city_pack._pull_neighborhoods",
        lambda _bbox: pytest.fail("a fictional pack must not query OpenStreetMap"),
    )
    build_pack(config, output, offline=False)

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    neighborhoods = json.loads((output / "neighborhoods.json").read_text(encoding="utf-8"))
    landmarks = json.loads((output / "landmarks.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in neighborhoods}

    assert manifest["fictional"] is True
    assert "openstreetmap" not in manifest["source"].lower()
    assert manifest["version"] == "0.1.0"
    assert by_id["mill-reach"]["adjacent_to"] == ["commons-bank"]
    assert by_id["commons-bank"]["adjacent_to"] == ["mill-reach", "orchard-row", "pineward-edge"]
    assert {item["grounding"] for item in neighborhoods + landmarks} == {"fictional"}
