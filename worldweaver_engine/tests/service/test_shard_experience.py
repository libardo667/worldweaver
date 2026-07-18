import json
from pathlib import Path

import pytest

from src.services.shard_experience import (
    DisabledStake,
    ShardExperienceConfigurationError,
    load_shard_experience,
)


def _valid_declaration() -> dict:
    return {
        "schema": "worldweaver.shard-experience",
        "schema_version": 1,
        "experience_type": "game",
        "ruleset": {"id": "test-private-town", "version": "0.1.0"},
        "entry_disclosure": {
            "title": "Test private game town",
            "summary": "A plainly disclosed test game with persistent constructive consequences.",
        },
        "capabilities": ["durable_objects", "custody", "placement"],
        "enabled_stakes": [],
        "disabled_stakes": [item.value for item in DisabledStake],
        "cross_boundary_policy": {
            "objects": "stay_on_shard",
            "conditions": "stay_on_shard",
            "obligations": "stay_on_shard",
        },
        "migration_policy": {
            "mode": "explicit_reentry",
            "notice": "Everyone must see and accept changed rules before entering this shard again.",
        },
    }


@pytest.mark.parametrize(
    ("shard_id", "shard_type"),
    [
        ("ww_pdx", "city"),
        ("ww_sfo", "city"),
        ("resident-hearth", "hearth"),
        ("ww_world", "world"),
    ],
)
def test_ordinary_shards_do_not_acquire_game_rules(shard_id, shard_type):
    experience = load_shard_experience(None, shard_id=shard_id, shard_type=shard_type)

    assert experience.shard_id == shard_id
    assert experience.shard_type == shard_type
    assert experience.experience_type == "commons"
    assert experience.declared is False
    assert experience.game_rules_active is False
    assert experience.ruleset is None
    assert experience.entry_disclosure.capabilities == []
    assert experience.entry_disclosure.enabled_stakes == []
    assert experience.entry_disclosure.disabled_stakes == []


def test_game_declaration_becomes_plain_language_entry_disclosure(tmp_path):
    path = tmp_path / "experience.json"
    path.write_text(json.dumps(_valid_declaration()), encoding="utf-8")

    experience = load_shard_experience(path, shard_id="private-town", shard_type="city")

    assert experience.experience_type == "game"
    assert experience.game_rules_active is True
    assert experience.ruleset is not None
    assert experience.ruleset.id == "test-private-town"
    assert experience.ruleset.version == "0.1.0"
    assert [item.id for item in experience.entry_disclosure.capabilities] == ["durable_objects", "custody", "placement"]
    assert experience.entry_disclosure.enabled_stakes == []
    assert {item.id for item in experience.entry_disclosure.disabled_stakes} == {item.value for item in DisabledStake}
    assert all(item.title and item.description for item in experience.entry_disclosure.disabled_stakes)
    assert "stay on this shard" in str(experience.entry_disclosure.boundary_notice)


def test_game_declaration_must_disable_every_phase_zero_stake(tmp_path):
    declaration = _valid_declaration()
    declaration["disabled_stakes"].remove("forced_loss")
    path = tmp_path / "unsafe-experience.json"
    path.write_text(json.dumps(declaration), encoding="utf-8")

    with pytest.raises(ShardExperienceConfigurationError, match="forced_loss"):
        load_shard_experience(path, shard_id="private-town", shard_type="city")


def test_game_declaration_cannot_enable_a_harmful_stake(tmp_path):
    declaration = _valid_declaration()
    declaration["enabled_stakes"] = ["injury"]
    path = tmp_path / "harmful-experience.json"
    path.write_text(json.dumps(declaration), encoding="utf-8")

    with pytest.raises(ShardExperienceConfigurationError, match="does not permit enabled harmful stakes"):
        load_shard_experience(path, shard_id="private-town", shard_type="city")


def test_configured_declaration_never_silently_falls_back(tmp_path):
    missing_path = tmp_path / "missing.json"

    with pytest.raises(ShardExperienceConfigurationError, match="Cannot read"):
        load_shard_experience(missing_path, shard_id="private-town", shard_type="city")


def test_game_declaration_rejects_unknown_capabilities(tmp_path):
    declaration = _valid_declaration()
    declaration["capabilities"].append("narration_changes_reality")
    path = tmp_path / "unknown-capability.json"
    path.write_text(json.dumps(declaration), encoding="utf-8")

    with pytest.raises(ShardExperienceConfigurationError, match="narration_changes_reality"):
        load_shard_experience(path, shard_id="private-town", shard_type="city")


def test_stoop_capability_requires_object_placement(tmp_path):
    declaration = _valid_declaration()
    declaration["capabilities"].append("stoops")
    declaration["capabilities"].remove("placement")
    path = tmp_path / "unimplemented-capability.json"
    path.write_text(json.dumps(declaration), encoding="utf-8")

    with pytest.raises(ShardExperienceConfigurationError, match="stoops also requires: placement"):
        load_shard_experience(path, shard_id="private-town", shard_type="city")


def test_game_declaration_rejects_materials_used_as_resident_needs(tmp_path):
    example_path = Path(__file__).resolve().parents[2] / "data" / "rulesets" / "private_constructive_game.v1.example.json"
    declaration = json.loads(example_path.read_text(encoding="utf-8"))
    declaration["materials"][0]["used_for_resident_need"] = True
    path = tmp_path / "resident-need-material.json"
    path.write_text(json.dumps(declaration), encoding="utf-8")

    with pytest.raises(ShardExperienceConfigurationError, match="used_for_resident_need"):
        load_shard_experience(path, shard_id="private-town", shard_type="city")


def test_game_declaration_rejects_recipe_with_unknown_material(tmp_path):
    example_path = Path(__file__).resolve().parents[2] / "data" / "rulesets" / "private_constructive_game.v1.example.json"
    declaration = json.loads(example_path.read_text(encoding="utf-8"))
    declaration["recipes"][0]["inputs"] = {"imaginary_ore": 1}
    path = tmp_path / "unknown-recipe-material.json"
    path.write_text(json.dumps(declaration), encoding="utf-8")

    with pytest.raises(ShardExperienceConfigurationError, match="unknown materials.*imaginary_ore"):
        load_shard_experience(path, shard_id="private-town", shard_type="city")
