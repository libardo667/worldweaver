# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.services.city_draft_store import CityDraftStore

ENGINE_ROOT = Path(__file__).resolve().parents[2]


def _alderbank_config() -> dict:
    path = ENGINE_ROOT / "scripts" / "city_configs" / "alderbank.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_draft_store_saves_valid_preview_away_from_published_packs(tmp_path):
    drafts = tmp_path / "city_drafts"
    store = CityDraftStore(drafts)
    config = _alderbank_config()
    original = copy.deepcopy(config)

    draft = store.create(config, now="2026-07-19T01:00:00Z")

    assert config == original
    assert draft.draft_id == "alderbank"
    assert draft.metadata["valid"] is True
    assert draft.metadata["draft_revision"] == 0
    assert draft.metadata["artifact_sha256"]
    assert (drafts / "alderbank" / "source.json").exists()
    assert (drafts / "alderbank" / "preview" / "generated_map.json").exists()
    assert (drafts / "alderbank" / "preview" / "generated_map.svg").exists()
    section_preview = (drafts / "alderbank" / "preview" / "sections" / "section-0-0.svg").read_text(encoding="utf-8")
    assert 'viewBox="0 0 18 18"' in section_preview
    assert store.list() == (draft.metadata,)

    loaded = store.get("alderbank")
    assert loaded.metadata == draft.metadata
    assert loaded.preview.files["generated_map.json"]["artifact_sha256"] == draft.metadata["artifact_sha256"]


def test_section_edits_rebuild_only_the_draft(tmp_path):
    store = CityDraftStore(tmp_path / "city_drafts")
    original = store.create(_alderbank_config(), now="2026-07-19T01:00:00Z")

    unlocked = store.edit_section(
        "alderbank",
        section_id="section-0-0",
        action="unlock",
        now="2026-07-19T01:01:00Z",
    )
    rerolled = store.edit_section(
        "alderbank",
        section_id="section-0-0",
        action="reroll",
        now="2026-07-19T01:02:00Z",
    )

    assert original.metadata["draft_revision"] == 0
    assert unlocked.metadata["draft_revision"] == 1
    assert rerolled.metadata["draft_revision"] == 2
    original_sections = {section["id"]: section for section in original.preview.files["generated_map.json"]["sections"]}
    rerolled_sections = {section["id"]: section for section in rerolled.preview.files["generated_map.json"]["sections"]}
    assert rerolled_sections["section-0-0"]["revision"] == 1
    assert rerolled_sections["section-0-0"]["detail"]["sha256"] != original_sections["section-0-0"]["detail"]["sha256"]
    for section_id in original_sections.keys() - {"section-0-0"}:
        assert rerolled_sections[section_id] == original_sections[section_id]


def test_failed_or_unsafe_draft_edits_leave_the_saved_draft_unchanged(tmp_path):
    store = CityDraftStore(tmp_path / "city_drafts")
    original = store.create(_alderbank_config(), now="2026-07-19T01:00:00Z")

    with pytest.raises(ValueError, match="is locked"):
        store.edit_section("alderbank", section_id="section-0-0", action="reroll")
    with pytest.raises(ValueError, match="draft ID"):
        store.get("../cities/alderbank")

    loaded = store.get("alderbank")
    assert loaded.metadata == original.metadata
    assert loaded.source == original.source


def test_draft_store_refuses_to_replace_an_existing_draft(tmp_path):
    store = CityDraftStore(tmp_path / "city_drafts")
    store.create(_alderbank_config(), now="2026-07-19T01:00:00Z")

    with pytest.raises(FileExistsError, match="already exists"):
        store.create(_alderbank_config(), now="2026-07-19T01:01:00Z")


def test_draft_store_detects_a_stale_non_map_preview_file(tmp_path):
    drafts = tmp_path / "city_drafts"
    store = CityDraftStore(drafts)
    store.create(_alderbank_config(), now="2026-07-19T01:00:00Z")
    stoops_path = drafts / "alderbank" / "preview" / "stoops.json"
    stoops_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="stoops.json no longer matches"):
        store.get("alderbank")


def test_draft_store_rejects_an_edit_based_on_a_stale_revision(tmp_path):
    store = CityDraftStore(tmp_path / "city_drafts")
    store.create(_alderbank_config(), now="2026-07-19T01:00:00Z")
    store.edit_section(
        "alderbank",
        section_id="section-0-0",
        action="unlock",
        expected_revision=0,
        now="2026-07-19T01:01:00Z",
    )

    with pytest.raises(ValueError, match="expected revision 0, found 1"):
        store.edit_section(
            "alderbank",
            section_id="section-0-0",
            action="reroll",
            expected_revision=0,
        )

    assert store.get("alderbank").metadata["draft_revision"] == 1
