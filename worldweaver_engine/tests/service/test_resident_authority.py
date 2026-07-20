from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from src.models import ResidentRequestNonce, SessionVars
from src.services.resident_authority import (
    ResidentAuthorityError,
    activate_resident_generation,
    authorize_resident_bootstrap_request,
    authorize_resident_request,
    bind_resident_identity,
    bind_resident_session,
)
from src.services.resident_protocol import (
    ResidentRuntimeCertificate,
    encoded_public_key,
    issue_runtime_certificate,
    signed_resident_request_headers,
)

NOW = 1_784_544_000
ACTOR_ID = "actor-123"
HEARTH_ID = "hearth:actor-123"
SESSION_ID = "resident-session"
AUDIENCE = "ww_alderbank"
TARGET = "/api/world/location/Commons/chat"
BODY = b'{"session_id":"resident-session","message":"hello"}'
BOOTSTRAP_TARGET = "/api/session/bootstrap"
BOOTSTRAP_BODY = b'{"session_id":"new-resident-session","actor_id":"actor-123"}'


def _certificate(identity_private, runtime_private, *, generation=1, audience=AUDIENCE):
    return issue_runtime_certificate(
        identity_private_key=identity_private,
        runtime_public_key=runtime_private.public_key(),
        actor_id=ACTOR_ID,
        hearth_shard_id=HEARTH_ID,
        runtime_generation=generation,
        audience=audience,
        scopes=["session.act", "session.bootstrap"],
        issued_at=NOW - 60,
        expires_at=NOW + 3600,
        certificate_id=f"certificate-{generation}",
    )


def _admit_and_bind(db_session, *, generation=1):
    identity_private = Ed25519PrivateKey.generate()
    runtime_private = Ed25519PrivateKey.generate()
    certificate = _certificate(
        identity_private,
        runtime_private,
        generation=generation,
    )
    bind_resident_identity(
        db_session,
        actor_id=ACTOR_ID,
        hearth_shard_id=HEARTH_ID,
        identity_public_key=encoded_public_key(identity_private.public_key()),
    )
    activate_resident_generation(
        db_session,
        certificate=certificate,
        expected_audience=AUDIENCE,
        now=NOW,
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
        runtime_generation=generation,
    )
    db_session.commit()
    return identity_private, runtime_private, certificate


def _headers(runtime_private, certificate, *, nonce="nonce-123"):
    return signed_resident_request_headers(
        runtime_private_key=runtime_private,
        certificate=certificate,
        method="POST",
        target=TARGET,
        body=BODY,
        timestamp=NOW,
        nonce=nonce,
    )


def _authorize(db_session, headers):
    return authorize_resident_request(
        db_session,
        session_id=SESSION_ID,
        expected_audience=AUDIENCE,
        required_scope="session.act",
        method="POST",
        target=TARGET,
        body=BODY,
        headers=headers,
        now=NOW,
    )


def _bootstrap_headers(runtime_private, certificate, *, nonce="bootstrap-nonce"):
    return signed_resident_request_headers(
        runtime_private_key=runtime_private,
        certificate=certificate,
        method="POST",
        target=BOOTSTRAP_TARGET,
        body=BOOTSTRAP_BODY,
        timestamp=NOW,
        nonce=nonce,
    )


def _authorize_bootstrap(db_session, headers, *, actor_id=ACTOR_ID):
    return authorize_resident_bootstrap_request(
        db_session,
        actor_id=actor_id,
        expected_audience=AUDIENCE,
        method="POST",
        target=BOOTSTRAP_TARGET,
        body=BOOTSTRAP_BODY,
        headers=headers,
        now=NOW,
    )


def test_identity_binding_is_idempotent_but_cannot_be_silently_replaced(db_session):
    identity_private = Ed25519PrivateKey.generate()
    public_key = encoded_public_key(identity_private.public_key())

    first = bind_resident_identity(
        db_session,
        actor_id=ACTOR_ID,
        hearth_shard_id=HEARTH_ID,
        identity_public_key=public_key,
        admission_reason="Synthetic identity reviewed for the protocol test.",
        admitted_by="test-steward",
    )
    second = bind_resident_identity(
        db_session,
        actor_id=ACTOR_ID,
        hearth_shard_id=HEARTH_ID,
        identity_public_key=public_key,
    )

    assert first is second
    assert (
        first.admission_reason == "Synthetic identity reviewed for the protocol test."
    )
    assert first.admitted_by == "test-steward"
    with pytest.raises(ResidentAuthorityError, match="different public continuity"):
        bind_resident_identity(
            db_session,
            actor_id=ACTOR_ID,
            hearth_shard_id=HEARTH_ID,
            identity_public_key=encoded_public_key(
                Ed25519PrivateKey.generate().public_key()
            ),
        )
    with pytest.raises(ResidentAuthorityError, match="another actor"):
        bind_resident_identity(
            db_session,
            actor_id="actor-456",
            hearth_shard_id="hearth:actor-456",
            identity_public_key=public_key,
        )
    with pytest.raises(ResidentAuthorityError, match="record why"):
        bind_resident_identity(
            db_session,
            actor_id="actor-789",
            hearth_shard_id="hearth:actor-789",
            identity_public_key=encoded_public_key(
                Ed25519PrivateKey.generate().public_key()
            ),
            admitted_by="local-steward",
        )


def test_generation_activation_requires_the_admitted_identity_hearth_and_city(
    db_session,
):
    identity_private = Ed25519PrivateKey.generate()
    runtime_private = Ed25519PrivateKey.generate()
    bind_resident_identity(
        db_session,
        actor_id=ACTOR_ID,
        hearth_shard_id=HEARTH_ID,
        identity_public_key=encoded_public_key(identity_private.public_key()),
    )

    wrong_city = _certificate(identity_private, runtime_private, audience="ww_portland")
    with pytest.raises(ResidentAuthorityError, match="audience"):
        activate_resident_generation(
            db_session,
            certificate=wrong_city,
            expected_audience=AUDIENCE,
            now=NOW,
        )

    wrong_signer = _certificate(Ed25519PrivateKey.generate(), runtime_private)
    with pytest.raises(ResidentAuthorityError, match="identity key"):
        activate_resident_generation(
            db_session,
            certificate=wrong_signer,
            expected_audience=AUDIENCE,
            now=NOW,
        )

    wrong_hearth_raw = _certificate(identity_private, runtime_private).to_dict()
    wrong_hearth_raw["hearth_shard_id"] = "hearth:other"
    # This object is deliberately no longer signature-valid, but the city can
    # reject the continuity mismatch before considering its signature.
    wrong_hearth = ResidentRuntimeCertificate.from_dict(wrong_hearth_raw)
    with pytest.raises(ResidentAuthorityError, match="different hearth"):
        activate_resident_generation(
            db_session,
            certificate=wrong_hearth,
            expected_audience=AUDIENCE,
            now=NOW,
        )


def test_first_signed_request_activates_an_admitted_runtime_without_creating_a_session(
    db_session,
):
    identity_private = Ed25519PrivateKey.generate()
    runtime_private = Ed25519PrivateKey.generate()
    certificate = _certificate(identity_private, runtime_private)
    bind_resident_identity(
        db_session,
        actor_id=ACTOR_ID,
        hearth_shard_id=HEARTH_ID,
        identity_public_key=encoded_public_key(identity_private.public_key()),
    )
    db_session.commit()

    verified = _authorize_bootstrap(
        db_session,
        _bootstrap_headers(runtime_private, certificate),
    )

    assert verified.actor_id == ACTOR_ID
    assert db_session.get(SessionVars, "new-resident-session") is None
    assert db_session.query(ResidentRequestNonce).count() == 1
    authority = bind_resident_identity(
        db_session,
        actor_id=ACTOR_ID,
        hearth_shard_id=HEARTH_ID,
        identity_public_key=encoded_public_key(identity_private.public_key()),
    )
    assert authority.active_runtime_generation == 1


def test_first_signed_request_rejects_unknown_or_mismatched_identity(db_session):
    identity_private = Ed25519PrivateKey.generate()
    runtime_private = Ed25519PrivateKey.generate()
    certificate = _certificate(identity_private, runtime_private)
    headers = _bootstrap_headers(runtime_private, certificate)

    with pytest.raises(ResidentAuthorityError) as unknown:
        _authorize_bootstrap(db_session, headers)
    assert unknown.value.code == "identity_not_admitted"

    bind_resident_identity(
        db_session,
        actor_id=ACTOR_ID,
        hearth_shard_id=HEARTH_ID,
        identity_public_key=encoded_public_key(identity_private.public_key()),
    )
    db_session.commit()
    with pytest.raises(ResidentAuthorityError) as mismatch:
        _authorize_bootstrap(db_session, headers, actor_id="actor-456")
    assert mismatch.value.code == "actor_mismatch"


def test_invalid_first_request_cannot_activate_generation_and_valid_proof_cannot_replay(
    db_session,
):
    identity_private = Ed25519PrivateKey.generate()
    runtime_private = Ed25519PrivateKey.generate()
    certificate = _certificate(identity_private, runtime_private)
    bind_resident_identity(
        db_session,
        actor_id=ACTOR_ID,
        hearth_shard_id=HEARTH_ID,
        identity_public_key=encoded_public_key(identity_private.public_key()),
    )
    db_session.commit()
    headers = _bootstrap_headers(runtime_private, certificate)

    with pytest.raises(ResidentAuthorityError) as changed_body:
        authorize_resident_bootstrap_request(
            db_session,
            actor_id=ACTOR_ID,
            expected_audience=AUDIENCE,
            method="POST",
            target=BOOTSTRAP_TARGET,
            body=b'{"changed":true}',
            headers=headers,
            now=NOW,
        )
    assert changed_body.value.code == "invalid_proof"
    authority = bind_resident_identity(
        db_session,
        actor_id=ACTOR_ID,
        hearth_shard_id=HEARTH_ID,
        identity_public_key=encoded_public_key(identity_private.public_key()),
    )
    assert authority.active_runtime_generation is None

    _authorize_bootstrap(db_session, headers)
    with pytest.raises(ResidentAuthorityError) as replay:
        _authorize_bootstrap(db_session, headers)
    assert replay.value.code == "replayed_request"


def test_session_binding_rejects_humans_wrong_actors_and_inactive_generations(
    db_session,
):
    _identity_private, _runtime_private, _certificate = _admit_and_bind(db_session)
    db_session.add(
        SessionVars(session_id="wrong-actor", actor_id="actor-other", vars={})
    )
    db_session.add(
        SessionVars(
            session_id="human-session",
            actor_id=ACTOR_ID,
            player_id="player-123",
            vars={},
        )
    )
    db_session.flush()

    with pytest.raises(ResidentAuthorityError, match="does not belong"):
        bind_resident_session(
            db_session,
            session_id="wrong-actor",
            actor_id=ACTOR_ID,
            runtime_generation=1,
        )
    with pytest.raises(ResidentAuthorityError, match="does not belong"):
        bind_resident_session(
            db_session,
            session_id="human-session",
            actor_id=ACTOR_ID,
            runtime_generation=1,
        )
    with pytest.raises(ResidentAuthorityError, match="not active"):
        bind_resident_session(
            db_session,
            session_id=SESSION_ID,
            actor_id=ACTOR_ID,
            runtime_generation=2,
        )


def test_authorized_request_consumes_nonce_once_and_keeps_it_after_caller_rollback(
    db_session,
):
    _identity_private, runtime_private, certificate = _admit_and_bind(db_session)
    headers = _headers(runtime_private, certificate)

    verified = _authorize(db_session, headers)
    db_session.rollback()

    assert verified.actor_id == ACTOR_ID
    assert db_session.query(ResidentRequestNonce).count() == 1
    with pytest.raises(ResidentAuthorityError) as replay:
        _authorize(db_session, headers)
    assert replay.value.code == "replayed_request"


def test_new_generation_fences_the_old_session_before_signature_verification(
    db_session,
):
    identity_private, old_runtime, old_certificate = _admit_and_bind(db_session)
    new_runtime = Ed25519PrivateKey.generate()
    new_certificate = _certificate(identity_private, new_runtime, generation=2)
    activate_resident_generation(
        db_session,
        certificate=new_certificate,
        expected_audience=AUDIENCE,
        now=NOW,
    )
    with pytest.raises(ResidentAuthorityError) as rollback:
        activate_resident_generation(
            db_session,
            certificate=old_certificate,
            expected_audience=AUDIENCE,
            now=NOW,
        )
    assert rollback.value.code == "retired_generation"
    db_session.commit()

    with pytest.raises(ResidentAuthorityError) as retired:
        _authorize(
            db_session,
            _headers(old_runtime, old_certificate, nonce="old-generation-nonce"),
        )
    assert retired.value.code == "retired_generation"
    assert db_session.query(ResidentRequestNonce).count() == 0


def test_authorization_refuses_to_commit_unrelated_pending_work(db_session):
    _identity_private, runtime_private, certificate = _admit_and_bind(db_session)
    db_session.add(SessionVars(session_id="unrelated", actor_id="actor-other", vars={}))

    with pytest.raises(ResidentAuthorityError) as dirty:
        _authorize(db_session, _headers(runtime_private, certificate))

    assert dirty.value.code == "authorization_session_dirty"
    db_session.rollback()
    assert db_session.get(SessionVars, "unrelated") is None
    assert db_session.query(ResidentRequestNonce).count() == 0
