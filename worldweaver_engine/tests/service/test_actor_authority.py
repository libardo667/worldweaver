from __future__ import annotations

import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

from src.models import Player, SessionVars
from src.services.actor_authority import (
    ActorAuthorizationError,
    RequestActorCredentials,
    authorize_session_actor,
    get_request_actor_credentials,
)
from src.services.auth_service import get_current_player_strict
from src.services.resident_authority import (
    activate_resident_generation,
    bind_resident_identity,
    bind_resident_session,
)
from src.services.resident_protocol import (
    RESIDENT_NONCE_HEADER,
    encoded_public_key,
    issue_runtime_certificate,
    signed_resident_request_headers,
)

ACTOR_ID = "actor-123"
SESSION_ID = "resident-session"
AUDIENCE = "ww_alderbank"
TARGET = "/api/world/make"
BODY = b'{"session_id":"resident-session"}'


def _credentials(*, player=None, headers=None, body=BODY, target=TARGET):
    return RequestActorCredentials(
        player=player,
        method="POST",
        target=target,
        body=body,
        resident_headers=headers or {},
    )


def _resident_setup(db_session):
    identity_private = Ed25519PrivateKey.generate()
    runtime_private = Ed25519PrivateKey.generate()
    certificate = issue_runtime_certificate(
        identity_private_key=identity_private,
        runtime_public_key=runtime_private.public_key(),
        actor_id=ACTOR_ID,
        hearth_shard_id="hearth:actor-123",
        runtime_generation=1,
        audience=AUDIENCE,
        scopes=["session.act", "session.bootstrap"],
    )
    bind_resident_identity(
        db_session,
        actor_id=ACTOR_ID,
        hearth_shard_id="hearth:actor-123",
        identity_public_key=encoded_public_key(identity_private.public_key()),
    )
    activate_resident_generation(
        db_session,
        certificate=certificate,
        expected_audience=AUDIENCE,
    )
    db_session.add(
        SessionVars(
            session_id=SESSION_ID,
            actor_id=ACTOR_ID,
            vars={"location": "Commons"},
        )
    )
    db_session.flush()
    bind_resident_session(
        db_session,
        session_id=SESSION_ID,
        actor_id=ACTOR_ID,
        runtime_generation=1,
    )
    db_session.commit()
    return runtime_private, certificate


def test_human_and_resident_proof_resolve_to_the_same_actor_shape(db_session):
    player = Player(
        id="player-123",
        actor_id=ACTOR_ID,
        email="person@example.test",
        username="person",
        display_name="Person",
        password_hash="unused",
    )
    db_session.add(player)
    db_session.add(
        SessionVars(
            session_id="human-session",
            player_id=player.id,
            actor_id=ACTOR_ID,
            vars={"location": "Commons"},
        )
    )
    db_session.commit()

    human = authorize_session_actor(
        db_session,
        credentials=_credentials(player=player),
        session_id="human-session",
        required_scope="session.act",
        expected_audience=AUDIENCE,
    )

    runtime_private, certificate = _resident_setup(db_session)
    headers = signed_resident_request_headers(
        runtime_private_key=runtime_private,
        certificate=certificate,
        method="POST",
        target=TARGET,
        body=BODY,
    )
    resident = authorize_session_actor(
        db_session,
        credentials=_credentials(headers=headers),
        session_id=SESSION_ID,
        required_scope="session.act",
        expected_audience=AUDIENCE,
    )

    assert human.actor_id == resident.actor_id == ACTOR_ID
    assert human.proof_kind == "human_jwt"
    assert human.player_id == "player-123"
    assert resident.proof_kind == "resident_signature"
    assert resident.runtime_generation == 1


def test_human_cannot_claim_another_session_and_anonymous_has_no_actor(db_session):
    player = Player(
        id="player-123",
        actor_id=ACTOR_ID,
        email="person@example.test",
        username="person",
        display_name="Person",
        password_hash="unused",
    )
    db_session.add(player)
    db_session.add(SessionVars(session_id="other-session", actor_id="actor-other", vars={}))
    db_session.commit()

    with pytest.raises(ActorAuthorizationError) as mismatch:
        authorize_session_actor(
            db_session,
            credentials=_credentials(player=player),
            session_id="other-session",
            required_scope="session.act",
        )
    assert mismatch.value.code == "session_actor_mismatch"
    assert mismatch.value.status_code == 403

    with pytest.raises(ActorAuthorizationError) as anonymous:
        authorize_session_actor(
            db_session,
            credentials=_credentials(),
            session_id="other-session",
            required_scope="session.act",
        )
    assert anonymous.value.code == "actor_proof_required"
    assert anonymous.value.status_code == 401


def test_resident_replay_keeps_the_shared_error_shape(db_session):
    runtime_private, certificate = _resident_setup(db_session)
    headers = signed_resident_request_headers(
        runtime_private_key=runtime_private,
        certificate=certificate,
        method="POST",
        target=TARGET,
        body=BODY,
        nonce="one-use-nonce",
    )
    proof = _credentials(headers=headers)

    authorize_session_actor(
        db_session,
        credentials=proof,
        session_id=SESSION_ID,
        required_scope="session.act",
        expected_audience=AUDIENCE,
    )
    with pytest.raises(ActorAuthorizationError) as replay:
        authorize_session_actor(
            db_session,
            credentials=proof,
            session_id=SESSION_ID,
            required_scope="session.act",
            expected_audience=AUDIENCE,
        )
    assert replay.value.code == "replayed_request"
    assert replay.value.status_code == 409


def test_request_dependency_preserves_body_and_exact_query_target():
    app = FastAPI()
    app.dependency_overrides[get_current_player_strict] = lambda: None

    @app.post("/probe/{item}")
    async def probe(
        item: str,
        payload: dict,
        credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
    ):
        return {
            "item": item,
            "parsed": payload,
            "captured": json.loads(credentials.body),
            "target": credentials.target,
        }

    with TestClient(app) as client:
        response = client.post(
            "/probe/caf%C3%A9?order=one&order=two",
            json={"hello": "world"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "item": "café",
        "parsed": {"hello": "world"},
        "captured": {"hello": "world"},
        "target": "/probe/caf%C3%A9?order=one&order=two",
    }


def test_request_dependency_rejects_mixed_human_and_resident_credentials():
    app = FastAPI()
    player = Player(
        id="player-123",
        actor_id=ACTOR_ID,
        email="person@example.test",
        username="person",
        display_name="Person",
        password_hash="unused",
    )
    app.dependency_overrides[get_current_player_strict] = lambda: player

    @app.post("/probe")
    async def probe(
        credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
    ):
        return {"proof": credentials.player is not None}

    with TestClient(app) as client:
        response = client.post("/probe", headers={RESIDENT_NONCE_HEADER: "partial-proof"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "ambiguous_actor_proof"
