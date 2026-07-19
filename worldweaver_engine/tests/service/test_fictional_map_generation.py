from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.build_city_pack import _build_landmarks, _build_neighborhoods
from src.services.map_generation import compile_fictional_map, edit_section


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
    assert all(section["locked"] is True for section in first.artifact["sections"])
    assert len(first.artifact["seams"]) == 17
    assert all(len(seam["sides"]) == 2 for seam in first.artifact["seams"])
    assert all(seam["sha256"] for seam in first.artifact["seams"])
    assert {connector["kind"] for seam in first.artifact["seams"] for connector in seam["connectors"]} == {
        "path",
        "river",
    }
    seam_references = {seam["id"]: sum(seam["id"] in section["seam_ids"] for section in first.artifact["sections"]) for seam in first.artifact["seams"]}
    assert set(seam_references.values()) == {2}
    sections_by_id = {section["id"]: section for section in first.artifact["sections"]}
    for seam in first.artifact["seams"]:
        for side in seam["sides"]:
            expected = [{**connector, "edge": side["edge"], "seam_id": seam["id"]} for connector in seam["connectors"]]
            actual = [connector for connector in sections_by_id[side["section_id"]]["connectors"] if connector["seam_id"] == seam["id"]]
            assert actual == expected
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
    by_route_id = {route["id"]: route for route in first.artifact["routes"]}
    assert by_route_id["path:commons-bank:orchard-row"]["via"] == ["alder-footbridge"]
    assert by_route_id["path:commons-bank:pineward-edge"]["path_type"] == "woodland_footpath"
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


def test_fictional_map_rejects_display_metadata_for_an_invented_path():
    config, neighborhoods, landmarks = _alderbank_inputs()
    config["fictional_map"]["route_styles"]["path:orchard-row:pineward-edge"] = {
        "name": "Invented shortcut",
        "path_type": "footpath",
    }

    with pytest.raises(ValueError, match="do not match canonical paths"):
        compile_fictional_map(config, neighborhoods=neighborhoods, landmarks=landmarks)


def test_one_unlocked_section_can_reroll_without_changing_core_fields_or_neighbors():
    config, neighborhoods, landmarks = _alderbank_inputs()
    baseline = compile_fictional_map(config, neighborhoods=neighborhoods, landmarks=landmarks).artifact

    with pytest.raises(ValueError, match="is locked"):
        edit_section(config, section_id="section-0-0", action="reroll")

    unlocked_config = edit_section(config, section_id="section-0-0", action="unlock")
    unlocked = compile_fictional_map(unlocked_config, neighborhoods=neighborhoods, landmarks=landmarks).artifact
    rerolled_config = edit_section(unlocked_config, section_id="section-0-0", action="reroll")
    rerolled = compile_fictional_map(rerolled_config, neighborhoods=neighborhoods, landmarks=landmarks).artifact

    assert unlocked["fields"] == baseline["fields"]
    assert rerolled["fields"] == baseline["fields"]
    assert rerolled["waterways"] == baseline["waterways"]
    assert rerolled["routes"] == baseline["routes"]
    assert rerolled["anchors"] == baseline["anchors"]
    assert rerolled["seams"] == baseline["seams"]

    baseline_sections = {section["id"]: section for section in baseline["sections"]}
    rerolled_sections = {section["id"]: section for section in rerolled["sections"]}
    assert rerolled_sections["section-0-0"]["revision"] == 1
    assert rerolled_sections["section-0-0"]["locked"] is False
    assert rerolled_sections["section-0-0"]["detail"]["sha256"] != baseline_sections["section-0-0"]["detail"]["sha256"]
    for section_id in baseline_sections.keys() - {"section-0-0"}:
        assert rerolled_sections[section_id] == baseline_sections[section_id]

    relocked_config = edit_section(rerolled_config, section_id="section-0-0", action="lock")
    relocked = compile_fictional_map(relocked_config, neighborhoods=neighborhoods, landmarks=landmarks).artifact
    relocked_section = next(section for section in relocked["sections"] if section["id"] == "section-0-0")
    assert relocked_section["locked"] is True
    assert relocked_section["revision"] == 1
    assert relocked_section["detail"] == rerolled_sections["section-0-0"]["detail"]


def test_section_overrides_cannot_name_space_outside_the_grid():
    config, neighborhoods, landmarks = _alderbank_inputs()
    config["fictional_map"]["sections"]["overrides"]["section-99-99"] = {"revision": 1, "locked": False}

    with pytest.raises(ValueError, match="unknown sections"):
        compile_fictional_map(config, neighborhoods=neighborhoods, landmarks=landmarks)


def test_section_controls_reject_ambiguous_lock_values():
    config, neighborhoods, landmarks = _alderbank_inputs()
    config["fictional_map"]["sections"]["default_locked"] = "false"

    with pytest.raises(ValueError, match="default_locked must be true or false"):
        compile_fictional_map(config, neighborhoods=neighborhoods, landmarks=landmarks)
    with pytest.raises(ValueError, match="default_locked must be true or false"):
        edit_section(config, section_id="section-0-0", action="unlock")
