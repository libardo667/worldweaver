# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from __future__ import annotations

import copy
import json
from pathlib import Path

from src.services.city_pack_builder import assemble_city_pack

ENGINE_ROOT = Path(__file__).resolve().parents[2]


def test_shared_builder_is_deterministic_and_does_not_mutate_its_draft():
    config_path = ENGINE_ROOT / "scripts" / "city_configs" / "alderbank.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    original = copy.deepcopy(config)
    built_at = "2026-07-19T00:00:00Z"

    first = assemble_city_pack(config, built_at=built_at)
    second = assemble_city_pack(config, built_at=built_at)

    assert first.files == second.files
    assert first.generated_map_svg == second.generated_map_svg
    assert first.validation.valid is True
    assert config == original
    assert first.files["manifest.json"]["built_at"] == built_at
    assert first.files["manifest.json"]["counts"]["map_sections"] == 12
    assert first.files["generated_map.json"]["artifact_sha256"]


def test_shared_builder_keeps_source_records_out_of_the_input_config():
    config_path = ENGINE_ROOT / "scripts" / "city_configs" / "portland.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    original = copy.deepcopy(config)
    source_neighborhood = {
        "name": "Test Quarter",
        "lat": 45.6,
        "lon": -122.8,
    }

    built = assemble_city_pack(
        config,
        osm_neighborhoods=[source_neighborhood],
        built_at="2026-07-19T00:00:00Z",
    )

    assert config == original
    assert source_neighborhood == {
        "name": "Test Quarter",
        "lat": 45.6,
        "lon": -122.8,
    }
    assert any(
        item["name"] == "Test Quarter" for item in built.files["neighborhoods.json"]
    )
