from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
import pytest

from src.models import Player
from src.services.identity_crypto import encrypt_text
from src.services.llm_client import (
    InferencePolicy,
    _resolve_api_key_for_policy,
    actor_private_policy,
    platform_shared_policy,
)
from src.services.player_api_keys import build_actor_private_inference_policy


def test_platform_shared_policy_uses_platform_key(monkeypatch):
    monkeypatch.setattr("src.services.llm_client.settings.openrouter_api_key", "sk-platform")

    key, source = _resolve_api_key_for_policy(platform_shared_policy(owner_id="shared-op"))

    assert key == "sk-platform"
    assert source == "platform"


def test_platform_shared_policy_rejects_actor_key():
    with pytest.raises(ValueError):
        _resolve_api_key_for_policy(
            InferencePolicy(
                owner_type="platform_shared",
                owner_id="bad-shared-op",
                actor_api_key="sk-actor",
                allow_actor_key=True,
                allow_platform_fallback=True,
            )
        )


def test_actor_private_policy_prefers_actor_key(monkeypatch):
    monkeypatch.setattr("src.services.llm_client.settings.openrouter_api_key", "sk-platform")

    key, source = _resolve_api_key_for_policy(
        actor_private_policy(
            owner_id="actor-123",
            actor_api_key="sk-actor",
            allow_platform_fallback=True,
        )
    )

    assert key == "sk-actor"
    assert source == "actor"


def test_actor_private_policy_can_fallback_to_platform(monkeypatch):
    monkeypatch.setattr("src.services.llm_client.settings.openrouter_api_key", "sk-platform")

    key, source = _resolve_api_key_for_policy(
        actor_private_policy(
            owner_id="actor-123",
            actor_api_key=None,
            allow_platform_fallback=True,
        )
    )

    assert key == "sk-platform"
    assert source == "platform"


def test_build_actor_private_policy_uses_player_key(db_session, monkeypatch):
    monkeypatch.setattr(
        "src.services.player_api_keys.settings.demo_key_expires_at",
        (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    )

    player = Player(
        actor_id="actor-byok-1",
        email="byok1@example.com",
        username="byok1",
        display_name="BYOK One",
        password_hash="hashed",
        api_key_enc=encrypt_text("sk-player-123"),
    )
    db_session.add(player)
    db_session.commit()

    policy = build_actor_private_inference_policy(db_session, player, owner_id="fallback-owner")

    assert policy.owner_type == "actor_private"
    assert policy.owner_id == "actor-byok-1"
    assert policy.actor_api_key == "sk-player-123"
    assert policy.allow_platform_fallback is False


def test_build_actor_private_policy_raises_after_demo_expiry_without_key(db_session, monkeypatch):
    monkeypatch.setattr(
        "src.services.player_api_keys.settings.demo_key_expires_at",
        (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    )

    with pytest.raises(HTTPException) as exc_info:
        build_actor_private_inference_policy(db_session, None, owner_id="anon-session")

    assert getattr(exc_info.value, "status_code", None) == 402
