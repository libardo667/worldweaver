from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.build_city_pack import _build_landmarks, _build_neighborhoods
from src.services.map_generation import compile_fictional_map


def _alderbank_inputs() -> tuple[dict, list[dict], list[dict]]:
    engine_root = Path(__file__).resolve().parents[2]
    config = json.loads((engine_root / "scripts" / "city_configs" / "alderbank.json").read_text(encoding="utf-8"))
    neighborhoods = _build_neighborhoods(copy.deepcopy(config["curated_neighborhoods"]), default_grounding="fictional")
    landmarks = _build_landmarks(copy.deepcopy(config["curated_landmarks"]), neighborhoods, default_grounding="fictional")
    return config, neighborhoods, landmarks


def test_alderbank_field_map_is_deterministic_and_sectioned():
    config, neighborhoods, landmarks = _alderbank_inputs()

    first = compile_fictional_map(config, neighborhoods=neighborhoods, landmarks=landmarks)
    second = compile_fictional_map(config, neighborhoods=neighborhoods, landmarks=landmarks)

    assert first == second
    assert first.artifact["grid"] == {"width": 72, "height": 54, "section_size": 18}
    assert len(first.artifact["sections"]) == 12
    assert all(section["seed"] for section in first.artifact["sections"])
    assert {field for field in first.artifact["fields"]} == {
        "elevation",
        "slope",
        "water_flow",
        "wetness",
        "soil",
        "region",
    }
    assert {anchor["id"] for anchor in first.artifact["anchors"]} == {
        *(neighborhood["id"] for neighborhood in neighborhoods),
        *(landmark["id"] for landmark in landmarks),
    }
    assert {route["kind"] for route in first.artifact["routes"]} == {"path"}
    assert any(connector["kind"] == "river" for section in first.artifact["sections"] for connector in section["connectors"])


def test_changing_the_authored_seed_changes_the_map_without_changing_city_facts():
    config, neighborhoods, landmarks = _alderbank_inputs()
    first = compile_fictional_map(config, neighborhoods=neighborhoods, landmarks=landmarks)
    changed = copy.deepcopy(config)
    changed["fictional_map"]["seed"] = "alderbank-fields-v2-test"

    second = compile_fictional_map(changed, neighborhoods=neighborhoods, landmarks=landmarks)

    assert first.artifact["artifact_sha256"] != second.artifact["artifact_sha256"]
    assert first.svg != second.svg
    assert first.artifact["anchors"] == second.artifact["anchors"]
    assert first.artifact["routes"] == second.artifact["routes"]


def test_encoded_fields_match_the_declared_grid_shape():
    config, neighborhoods, landmarks = _alderbank_inputs()
    artifact = compile_fictional_map(config, neighborhoods=neighborhoods, landmarks=landmarks).artifact

    for name, field in artifact["fields"].items():
        assert len(field["rows"]) == artifact["grid"]["height"]
        row_width = artifact["grid"]["width"] * (2 if field["encoding"] == "hex-u8-rows" else 1)
        assert {len(row) for row in field["rows"]} == {row_width}, name


def test_fictional_map_rejects_bounds_that_would_letterbox_the_svg():
    config, neighborhoods, landmarks = _alderbank_inputs()
    config["bboxes"]["default"] = "45.0000,-122.0200,45.0300,-121.9800"

    with pytest.raises(ValueError, match="must match the grid aspect"):
        compile_fictional_map(config, neighborhoods=neighborhoods, landmarks=landmarks)
