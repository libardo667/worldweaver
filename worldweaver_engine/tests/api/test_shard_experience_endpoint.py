"""Tests for the public, pre-entry shard rules disclosure."""

from pathlib import Path

from src.config import settings


def test_public_experience_endpoint_discloses_ordinary_shard(client, monkeypatch):
    monkeypatch.setattr(settings, "shard_experience_path", None)
    monkeypatch.setattr(settings, "shard_id", "ww_pdx")
    monkeypatch.setattr(settings, "shard_type", "city")

    response = client.get("/api/shard/experience")

    assert response.status_code == 200
    payload = response.json()
    assert payload["shard_id"] == "ww_pdx"
    assert payload["experience_type"] == "commons"
    assert payload["game_rules_active"] is False
    assert payload["ruleset"] is None
    assert payload["entry_disclosure"]["capabilities"] == []


def test_public_experience_endpoint_discloses_configured_game_rules(client, monkeypatch):
    example = Path(__file__).resolve().parents[2] / "data" / "rulesets" / "private_constructive_game.v1.example.json"
    monkeypatch.setattr(settings, "shard_experience_path", str(example))
    monkeypatch.setattr(settings, "shard_id", "private-game-town")
    monkeypatch.setattr(settings, "shard_type", "city")

    response = client.get("/api/shard/experience")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "worldweaver.shard-experience"
    assert payload["schema_version"] == 1
    assert payload["experience_type"] == "game"
    assert payload["game_rules_active"] is True
    assert payload["ruleset"] == {"id": "private-constructive-town", "version": "0.1.0"}
    assert payload["entry_disclosure"]["enabled_stakes"] == []
    assert len(payload["entry_disclosure"]["disabled_stakes"]) == 11
    assert payload["entry_disclosure"]["boundary_notice"]


def test_public_experience_endpoint_has_no_private_runtime_fields(client, monkeypatch):
    monkeypatch.setattr(settings, "shard_experience_path", None)

    payload = client.get("/api/shard/experience").json()
    serialized = str(payload).lower()

    for private_name in ("prompt", "memory", "arousal", "model_trace", "ledger"):
        assert private_name not in serialized
