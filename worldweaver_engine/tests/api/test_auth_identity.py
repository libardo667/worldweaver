from datetime import datetime, timedelta, timezone

from jose import jwt

from src.config import settings
from src.models import FederationActor, FederationActorAuth, Player, SessionVars
from src.services.auth_service import ALGORITHM
from src.services.request_limits import FixedWindowRateLimiter


def test_register_creates_actor_identity_and_local_projection(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )

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

    player = (
        db_session.query(Player).filter(Player.actor_id == payload["actor_id"]).first()
    )
    actor = db_session.get(FederationActor, payload["actor_id"])
    auth = db_session.get(FederationActorAuth, payload["actor_id"])

    assert player is not None
    assert actor is not None
    assert auth is not None
    assert actor.display_name == "Test User"
    assert auth.username == "testuser"
    assert auth.pass_type == "citizen"
    assert auth.pass_expires_at is None
    assert player.pass_type == "citizen"
    assert player.pass_expires_at is None


def test_email_first_registration_requires_matching_confirmation_and_name_before_entry(
    client, db_session, monkeypatch
):
    welcomes: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email",
        lambda email, name: welcomes.append((email, name)),
    )

    mismatch = client.post(
        "/api/auth/register",
        json={
            "email": "mismatch@example.com",
            "password": "supersecret1",
            "password_confirmation": "different-secret",
            "terms_accepted": True,
        },
    )
    assert mismatch.status_code == 422
    assert (
        db_session.query(FederationActorAuth)
        .filter(FederationActorAuth.email == "mismatch@example.com")
        .first()
        is None
    )

    registered = client.post(
        "/api/auth/register",
        json={
            "email": "email-first@example.com",
            "password": "supersecret1",
            "password_confirmation": "supersecret1",
            "terms_accepted": True,
        },
    )
    assert registered.status_code == 200
    payload = registered.json()
    assert payload["email"] == "email-first@example.com"
    assert payload["username"].startswith("ww_")
    assert payload["display_name"] == "New arrival"
    assert payload["profile_complete"] is False
    assert welcomes == []

    blocked = client.post(
        "/api/session/bootstrap",
        json={
            "session_id": "email-first-session",
            "player_role": "New arrival",
            "bootstrap_source": "commons_client",
        },
        headers={"Authorization": f"Bearer {payload['token']}"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "profile_incomplete"

    completed = client.patch(
        "/api/auth/profile",
        json={"display_name": "River"},
        headers={"Authorization": f"Bearer {payload['token']}"},
    )
    assert completed.status_code == 200
    assert completed.json()["display_name"] == "River"
    assert completed.json()["profile_complete"] is True
    assert welcomes == [("email-first@example.com", "River")]
    auth = db_session.get(FederationActorAuth, payload["actor_id"])
    assert auth.profile_completed_at is not None


def test_required_email_verification_precedes_public_name_and_city_entry(
    client, db_session, monkeypatch
):
    delivered: list[tuple[str, str]] = []
    monkeypatch.setattr(settings, "require_email_verification", True)
    monkeypatch.setattr(settings, "resend_api_key", "test-resend-key")
    monkeypatch.setattr(settings, "resend_from_email", "hello@example.test")
    monkeypatch.setattr(
        "src.api.auth.routes.send_email_verification",
        lambda email, token: delivered.append((email, token)),
    )
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )

    registered = client.post(
        "/api/auth/register",
        json={
            "email": "verify-first@example.com",
            "password": "supersecret1",
            "password_confirmation": "supersecret1",
            "terms_accepted": True,
        },
    )
    assert registered.status_code == 200
    payload = registered.json()
    assert payload["email_verified"] is False
    assert payload["email_verification_required"] is True
    assert payload["profile_complete"] is False
    assert len(delivered) == 1
    assert delivered[0][0] == "verify-first@example.com"
    verification_token = delivered[0][1]

    auth = db_session.get(FederationActorAuth, payload["actor_id"])
    assert auth.email_verified_at is None
    assert auth.email_verification_token_hash
    assert verification_token not in auth.email_verification_token_hash

    resent = client.post(
        "/api/auth/resend-verification",
        headers={"Authorization": f"Bearer {payload['token']}"},
    )
    assert resent.status_code == 200
    assert len(delivered) == 1

    headers = {"Authorization": f"Bearer {payload['token']}"}
    blocked_profile = client.patch(
        "/api/auth/profile",
        json={"display_name": "River"},
        headers=headers,
    )
    assert blocked_profile.status_code == 409
    assert blocked_profile.json()["detail"] == "email_unverified"

    blocked_entry = client.post(
        "/api/session/bootstrap",
        json={
            "session_id": "unverified-session",
            "player_role": "New arrival",
            "bootstrap_source": "commons_client",
        },
        headers=headers,
    )
    assert blocked_entry.status_code == 409
    assert blocked_entry.json()["detail"] == "email_unverified"

    rejected = client.post(
        "/api/auth/verify-email", json={"token": "not-the-right-token"}
    )
    assert rejected.status_code == 401
    verified = client.post("/api/auth/verify-email", json={"token": verification_token})
    assert verified.status_code == 200
    verified_payload = verified.json()
    assert verified_payload["email_verified"] is True
    assert verified_payload["profile_complete"] is False

    reused = client.post("/api/auth/verify-email", json={"token": verification_token})
    assert reused.status_code == 401

    completed = client.patch(
        "/api/auth/profile",
        json={"display_name": "River"},
        headers={"Authorization": f"Bearer {verified_payload['token']}"},
    )
    assert completed.status_code == 200
    assert completed.json()["display_name"] == "River"
    assert completed.json()["profile_complete"] is True


def test_required_email_verification_refuses_registration_without_delivery(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "require_email_verification", True)
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "resend_from_email", "")

    response = client.post(
        "/api/auth/register",
        json={
            "email": "stranded@example.com",
            "password": "supersecret1",
            "password_confirmation": "supersecret1",
            "terms_accepted": True,
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "email_verification_delivery_unavailable"
    assert (
        db_session.query(FederationActorAuth)
        .filter(FederationActorAuth.email == "stranded@example.com")
        .first()
        is None
    )


def test_auth_me_rejects_legacy_player_token(client, monkeypatch):
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )
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
    legacy_token = jwt.encode(
        {"sub": player_id}, settings.jwt_secret, algorithm=ALGORITHM
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {legacy_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "legacy_auth_token"


def test_session_bootstrap_rejects_legacy_player_token(client, monkeypatch):
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )
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
    legacy_token = jwt.encode(
        {"sub": player_id}, settings.jwt_secret, algorithm=ALGORITHM
    )

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


def test_login_accepts_email_or_username(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )
    register = client.post(
        "/api/auth/register",
        json={
            "email": "multi-login@example.com",
            "username": "multilogin",
            "display_name": "Multi Login",
            "password": "supersecret1",
            "pass_type": "visitor_7day",
            "terms_accepted": True,
        },
    )
    assert register.status_code == 200

    login_by_username = client.post(
        "/api/auth/login",
        json={"identifier": "multilogin", "password": "supersecret1"},
    )
    assert login_by_username.status_code == 200

    login_by_email = client.post(
        "/api/auth/login",
        json={"identifier": "multi-login@example.com", "password": "supersecret1"},
    )
    assert login_by_email.status_code == 200
    assert login_by_email.json()["actor_id"] == register.json()["actor_id"]


def test_authenticated_human_can_correct_public_display_name(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )
    register = client.post(
        "/api/auth/register",
        json={
            "email": "rename-me@example.com",
            "username": "renameme",
            "display_name": "Wrong Name",
            "password": "supersecret1",
            "terms_accepted": True,
        },
    )
    actor_id = register.json()["actor_id"]
    player = db_session.query(Player).filter(Player.actor_id == actor_id).one()
    session = SessionVars(
        session_id="rename-me-session",
        player_id=player.id,
        actor_id=actor_id,
        vars={
            "name": "Wrong Name",
            "player_role": "Wrong Name",
            "character_profile": "Wrong Name",
            "location": "Commons Bank",
        },
    )
    db_session.add(session)
    db_session.commit()

    updated = client.patch(
        "/api/auth/profile",
        json={"display_name": "Right Name"},
        headers={"Authorization": f"Bearer {register.json()['token']}"},
    )

    assert updated.status_code == 200
    assert updated.json()["actor_id"] == actor_id
    assert updated.json()["display_name"] == "Right Name"
    assert db_session.get(FederationActor, actor_id).display_name == "Right Name"
    assert (
        db_session.query(Player).filter(Player.actor_id == actor_id).one().display_name
        == "Right Name"
    )
    db_session.refresh(session)
    assert session.vars["name"] == "Right Name"
    assert session.vars["player_role"] == "Right Name"
    assert session.vars["character_profile"] == "Right Name"


def test_login_does_not_move_the_actor_to_the_authenticating_shard(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )
    register = client.post(
        "/api/auth/register",
        json={
            "email": "still-there@example.com",
            "username": "stillthere",
            "display_name": "Still There",
            "password": "supersecret1",
            "terms_accepted": True,
        },
    )
    actor = db_session.get(FederationActor, register.json()["actor_id"])
    assert actor is not None
    actor.current_shard = "another-city"
    db_session.commit()

    login = client.post(
        "/api/auth/login",
        json={"identifier": "stillthere", "password": "supersecret1"},
    )

    assert login.status_code == 200
    db_session.refresh(actor)
    assert actor.current_shard == "another-city"


def test_ordinary_bootstrap_rejects_an_actor_attached_to_another_city(
    seeded_client,
    seeded_world_id,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )
    register = seeded_client.post(
        "/api/auth/register",
        json={
            "email": "elsewhere@example.com",
            "username": "elsewhere",
            "display_name": "Elsewhere",
            "password": "supersecret1",
            "terms_accepted": True,
        },
    )
    actor = db_session.get(FederationActor, register.json()["actor_id"])
    assert actor is not None
    actor.current_shard = "another-city"
    db_session.commit()

    response = seeded_client.post(
        "/api/session/bootstrap",
        json={
            "session_id": "elsewhere-session",
            "world_id": seeded_world_id,
            "player_role": "Elsewhere",
            "bootstrap_source": "commons_client",
        },
        headers={"Authorization": f"Bearer {register.json()['token']}"},
    )

    assert response.status_code == 409
    assert "federation travel" in response.json()["detail"]
    assert db_session.get(SessionVars, "elsewhere-session") is None


def test_ordinary_bootstrap_rejects_a_second_local_session_for_one_actor(
    seeded_client,
    seeded_world_id,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )
    register = seeded_client.post(
        "/api/auth/register",
        json={
            "email": "already-here@example.com",
            "username": "alreadyhere",
            "display_name": "Already Here",
            "password": "supersecret1",
            "terms_accepted": True,
        },
    )
    headers = {"Authorization": f"Bearer {register.json()['token']}"}
    first = seeded_client.post(
        "/api/session/bootstrap",
        json={
            "session_id": "already-here-one",
            "world_id": seeded_world_id,
            "player_role": "Already Here",
            "bootstrap_source": "commons_client",
        },
        headers=headers,
    )
    assert first.status_code == 200

    second = seeded_client.post(
        "/api/session/bootstrap",
        json={
            "session_id": "already-here-two",
            "world_id": seeded_world_id,
            "player_role": "Already Here",
            "bootstrap_source": "commons_client",
        },
        headers=headers,
    )

    assert second.status_code == 409
    assert "already present" in second.json()["detail"]
    assert db_session.get(SessionVars, "already-here-one") is not None
    assert db_session.get(SessionVars, "already-here-two") is None


def test_authenticated_actor_can_recover_existing_local_session(
    seeded_client,
    seeded_world_id,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )
    register = seeded_client.post(
        "/api/auth/register",
        json={
            "email": "recover-session@example.com",
            "username": "recoversession",
            "display_name": "Recover Session",
            "password": "supersecret1",
            "terms_accepted": True,
        },
    )
    headers = {"Authorization": f"Bearer {register.json()['token']}"}

    anonymous = seeded_client.get("/api/session/current")
    assert anonymous.status_code == 401

    absent = seeded_client.get("/api/session/current", headers=headers)
    assert absent.status_code == 200
    assert absent.json() == {"active": False, "session_id": None, "location": None}

    entered = seeded_client.post(
        "/api/session/bootstrap",
        json={
            "session_id": "recover-existing-session",
            "world_id": seeded_world_id,
            "player_role": "Recover Session",
            "bootstrap_source": "commons_client",
            "entry_location": "Recovery Gate",
        },
        headers=headers,
    )
    assert entered.status_code == 200

    recovered = seeded_client.get("/api/session/current", headers=headers)
    assert recovered.status_code == 200
    assert recovered.json() == {
        "active": True,
        "session_id": "recover-existing-session",
        "location": "Recovery Gate",
    }
    assert (
        db_session.query(SessionVars)
        .filter(SessionVars.actor_id == register.json()["actor_id"])
        .count()
        == 1
    )


def test_login_normalizes_legacy_visitor_passes(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )
    register = client.post(
        "/api/auth/register",
        json={
            "email": "legacy-pass@example.com",
            "username": "legacypass",
            "display_name": "Legacy Pass",
            "password": "supersecret1",
            "pass_type": "visitor_7day",
            "terms_accepted": True,
        },
    )
    assert register.status_code == 200
    actor_id = register.json()["actor_id"]

    auth = db_session.get(FederationActorAuth, actor_id)
    player = db_session.query(Player).filter(Player.actor_id == actor_id).first()
    assert auth is not None
    assert player is not None
    expired_at = datetime.now(timezone.utc) - timedelta(days=30)
    auth.pass_type = "visitor_7day"
    auth.pass_expires_at = expired_at
    player.pass_type = "visitor_7day"
    player.pass_expires_at = expired_at
    db_session.commit()

    login = client.post(
        "/api/auth/login",
        json={"identifier": "legacypass", "password": "supersecret1"},
    )

    assert login.status_code == 200
    payload = login.json()
    assert payload["pass_type"] == "citizen"
    assert payload["pass_expires_at"] is None
    db_session.expire_all()
    auth = db_session.get(FederationActorAuth, actor_id)
    player = db_session.query(Player).filter(Player.actor_id == actor_id).first()
    assert auth is not None
    assert player is not None
    assert auth.pass_type == "citizen"
    assert auth.pass_expires_at is None
    assert player.pass_type == "citizen"
    assert player.pass_expires_at is None


def test_password_reset_updates_federation_auth_and_allows_login(
    client, db_session, monkeypatch
):
    sent = {}

    def _fake_send_reset(to_email: str, display_name: str, reset_token: str) -> None:
        sent["to_email"] = to_email
        sent["display_name"] = display_name
        sent["reset_token"] = reset_token

    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "src.api.auth.routes.send_password_reset_email", _fake_send_reset
    )

    register = client.post(
        "/api/auth/register",
        json={
            "email": "reset-me@example.com",
            "username": "resetme",
            "display_name": "Reset Me",
            "password": "supersecret1",
            "pass_type": "visitor_7day",
            "terms_accepted": True,
        },
    )
    assert register.status_code == 200
    actor_id = register.json()["actor_id"]

    request_reset = client.post(
        "/api/auth/request-password-reset",
        json={"identifier": "reset-me@example.com"},
    )
    assert request_reset.status_code == 200
    assert request_reset.json()["ok"] is True
    assert sent["to_email"] == "reset-me@example.com"
    assert sent["display_name"] == "Reset Me"
    assert sent["reset_token"]

    auth = db_session.get(FederationActorAuth, actor_id)
    assert auth is not None
    assert auth.password_reset_token_hash
    assert auth.password_reset_expires_at is not None

    reset = client.post(
        "/api/auth/reset-password",
        json={"token": sent["reset_token"], "new_password": "newsupersecret1"},
    )
    assert reset.status_code == 200
    assert reset.json()["actor_id"] == actor_id

    db_session.expire_all()
    auth = db_session.get(FederationActorAuth, actor_id)
    assert auth is not None
    assert auth.password_reset_token_hash is None
    assert auth.password_reset_expires_at is None

    login = client.post(
        "/api/auth/login",
        json={"identifier": "resetme", "password": "newsupersecret1"},
    )
    assert login.status_code == 200
    assert login.json()["actor_id"] == actor_id


def test_account_entry_rate_limit_returns_retry_after(client, monkeypatch):
    monkeypatch.setattr("main.settings.auth_rate_limit_per_minute", 2)
    monkeypatch.setattr("main._auth_rate_limiter", FixedWindowRateLimiter())

    first = client.post(
        "/api/auth/login", json={"identifier": "missing", "password": "incorrect"}
    )
    second = client.post(
        "/api/auth/login", json={"identifier": "missing", "password": "incorrect"}
    )
    limited = client.post(
        "/api/auth/login", json={"identifier": "missing", "password": "incorrect"}
    )

    assert first.status_code == 401
    assert second.status_code == 401
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 1
