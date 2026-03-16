from jose import jwt

from src.config import settings
from src.models import FederationActor, FederationActorAuth, FederationActorSecret, Player
from src.services.auth_service import ALGORITHM
from src.services.identity_crypto import decrypt_text


def test_register_creates_actor_identity_and_local_projection(client, db_session, monkeypatch):
    monkeypatch.setattr("src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None)

    response = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "display_name": "Test User",
            "password": "supersecret1",
            "pass_type": "visitor_7day",
            "terms_accepted": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["actor_id"]
    assert payload["player_id"]

    player = db_session.query(Player).filter(Player.actor_id == payload["actor_id"]).first()
    actor = db_session.get(FederationActor, payload["actor_id"])
    auth = db_session.get(FederationActorAuth, payload["actor_id"])

    assert player is not None
    assert actor is not None
    assert auth is not None
    assert actor.display_name == "Test User"
    assert auth.username == "testuser"


def test_authenticated_settings_key_updates_actor_secret(client, db_session, monkeypatch):
    monkeypatch.setattr("src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None)
    register = client.post(
        "/api/auth/register",
        json={
            "email": "byok@example.com",
            "username": "byokuser",
            "display_name": "BYOK User",
            "password": "supersecret1",
            "pass_type": "visitor_7day",
            "terms_accepted": True,
        },
    )
    token = register.json()["token"]
    actor_id = register.json()["actor_id"]

    response = client.post(
        "/api/settings/key",
        json={"api_key": "sk-personal-test-key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    secret = db_session.get(FederationActorSecret, actor_id)
    player = db_session.query(Player).filter(Player.actor_id == actor_id).first()

    assert secret is not None
    assert player is not None
    assert decrypt_text(secret.llm_api_key_enc) == "sk-personal-test-key"
    assert decrypt_text(player.api_key_enc) == "sk-personal-test-key"


def test_auth_me_rejects_legacy_player_token(client, monkeypatch):
    monkeypatch.setattr("src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None)
    register = client.post(
        "/api/auth/register",
        json={
            "email": "legacy-auth@example.com",
            "username": "legacyauth",
            "display_name": "Legacy Auth",
            "password": "supersecret1",
            "pass_type": "visitor_7day",
            "terms_accepted": True,
        },
    )
    assert register.status_code == 200
    player_id = register.json()["player_id"]
    legacy_token = jwt.encode({"sub": player_id}, settings.jwt_secret, algorithm=ALGORITHM)

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {legacy_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "legacy_auth_token"


def test_settings_key_rejects_legacy_player_token(client, monkeypatch):
    monkeypatch.setattr("src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None)
    register = client.post(
        "/api/auth/register",
        json={
            "email": "legacy-settings@example.com",
            "username": "legacysettings",
            "display_name": "Legacy Settings",
            "password": "supersecret1",
            "pass_type": "visitor_7day",
            "terms_accepted": True,
        },
    )
    assert register.status_code == 200
    player_id = register.json()["player_id"]
    legacy_token = jwt.encode({"sub": player_id}, settings.jwt_secret, algorithm=ALGORITHM)
    settings.openrouter_api_key = ""

    response = client.post(
        "/api/settings/key",
        json={"api_key": "sk-should-not-stick"},
        headers={"Authorization": f"Bearer {legacy_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "legacy_auth_token"
    assert settings.openrouter_api_key == ""


def test_session_bootstrap_rejects_legacy_player_token(client, monkeypatch):
    monkeypatch.setattr("src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None)
    register = client.post(
        "/api/auth/register",
        json={
            "email": "legacy-bootstrap@example.com",
            "username": "legacybootstrap",
            "display_name": "Legacy Bootstrap",
            "password": "supersecret1",
            "pass_type": "visitor_7day",
            "terms_accepted": True,
        },
    )
    assert register.status_code == 200
    player_id = register.json()["player_id"]
    legacy_token = jwt.encode({"sub": player_id}, settings.jwt_secret, algorithm=ALGORITHM)

    response = client.post(
        "/api/session/bootstrap",
        json={
            "session_id": "legacy-bootstrap-session",
            "world_theme": "fogbound harbor",
            "player_role": "night ferryman",
            "bootstrap_source": "entry-screen",
        },
        headers={"Authorization": f"Bearer {legacy_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "legacy_auth_token"
