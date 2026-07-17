from __future__ import annotations

import json

from src.familiar.config import HearthConfig


def test_hearth_has_no_keeper_or_host_grants_without_config(tmp_path):
    config = HearthConfig.load(tmp_path)

    assert config.place == "the hearth"
    assert config.keeper == ""
    assert config.read_roots == ()
    assert config.weather is False
    assert config.vision is False


def test_hearth_config_resolves_relative_roots_from_the_resident_home(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (tmp_path / "hearth.json").write_text(
        json.dumps(
            {
                "place": "the window room",
                "keeper": "Levi",
                "read_roots": ["shared"],
                "weather": True,
                "vision": True,
            }
        ),
        encoding="utf-8",
    )

    config = HearthConfig.load(tmp_path)

    assert config.place == "the window room"
    assert config.keeper == "Levi"
    assert config.read_roots == (shared.resolve(),)
    assert config.weather is True
    assert config.vision is True
    assert config.source_path == tmp_path / "hearth.json"


def test_legacy_familiar_config_is_read_only_as_a_compatibility_name(tmp_path):
    (tmp_path / "familiar.json").write_text(
        json.dumps({"keeper": "Levi"}),
        encoding="utf-8",
    )

    config = HearthConfig.load(tmp_path)

    assert config.keeper == "Levi"
    assert config.source_path == tmp_path / "familiar.json"
