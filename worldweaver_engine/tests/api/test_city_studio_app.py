# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.city_studio_app import create_city_studio_app
from src.services.city_draft_store import CityDraftStore

ENGINE_ROOT = Path(__file__).resolve().parents[2]
TOKEN = "test-city-studio-token"


def _client(tmp_path: Path) -> tuple[TestClient, Path]:
    drafts = tmp_path / "city_drafts"
    app = create_city_studio_app(
        store=CityDraftStore(drafts),
        configurations_dir=(ENGINE_ROOT / "scripts" / "city_configs").resolve(),
        access_token=TOKEN,
        html_path=ENGINE_ROOT / "scripts" / "city_studio.html",
    )
    return TestClient(app), drafts


def _headers() -> dict[str, str]:
    return {"X-City-Studio-Token": TOKEN}


def test_city_studio_bootstraps_locally_but_protects_its_api(tmp_path):
    client, _ = _client(tmp_path)

    page = client.get("/")
    assert page.status_code == 200
    assert "WorldWeaver City Studio" in page.text
    assert TOKEN in page.text
    assert page.headers["cache-control"] == "no-store"
    assert client.get("/api/drafts").status_code == 401
    assert client.get("/api/drafts", headers=_headers()).json() == {"drafts": []}


def test_city_studio_creates_and_edits_only_a_private_draft(tmp_path):
    client, drafts = _client(tmp_path)
    published = tmp_path / "cities" / "alderbank"

    created = client.post("/api/drafts", headers=_headers(), json={"city": "alderbank"})
    assert created.status_code == 201
    payload = created.json()
    assert payload["metadata"]["draft_revision"] == 0
    assert len(payload["sections"]) == 12
    assert all(section["locked"] for section in payload["sections"])
    assert (drafts / "alderbank" / "preview" / "generated_map.svg").exists()
    assert not published.exists()

    map_response = client.get("/api/drafts/alderbank/map.svg", headers=_headers())
    assert map_response.status_code == 200
    assert map_response.headers["content-type"].startswith("image/svg+xml")
    section_response = client.get("/api/drafts/alderbank/sections/section-0-0.svg", headers=_headers())
    assert 'viewBox="0 0 18 18"' in section_response.text

    unlocked = client.post(
        "/api/drafts/alderbank/sections/section-0-0",
        headers=_headers(),
        json={"action": "unlock", "expected_revision": 0},
    )
    assert unlocked.status_code == 200
    assert unlocked.json()["metadata"]["draft_revision"] == 1
    selected = next(section for section in unlocked.json()["sections"] if section["id"] == "section-0-0")
    assert selected["locked"] is False

    stale = client.post(
        "/api/drafts/alderbank/sections/section-0-0",
        headers=_headers(),
        json={"action": "reroll", "expected_revision": 0},
    )
    assert stale.status_code == 409
    assert "expected revision 0, found 1" in stale.json()["detail"]
    assert not published.exists()


def test_city_studio_rejects_unknown_or_escaped_configuration_names(tmp_path):
    client, _ = _client(tmp_path)

    unknown = client.post("/api/drafts", headers=_headers(), json={"city": "not-a-city"})
    escaped = client.post("/api/drafts", headers=_headers(), json={"city": "../alderbank"})

    assert unknown.status_code == 404
    assert escaped.status_code == 404


def test_city_studio_keeps_real_city_drafts_valid_without_claiming_a_generated_map(
    tmp_path,
):
    client, _ = _client(tmp_path)

    created = client.post("/api/drafts", headers=_headers(), json={"city": "portland"})

    assert created.status_code == 201
    assert created.json()["validation"]["valid"] is True
    assert created.json()["map_available"] is False
    assert client.get("/api/drafts/portland/map.svg", headers=_headers()).status_code == 404


def test_city_studio_rejects_untrusted_host_headers(tmp_path):
    client, _ = _client(tmp_path)

    response = client.get("/", headers={"Host": "example.com"})

    assert response.status_code == 400
