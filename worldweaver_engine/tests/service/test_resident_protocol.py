from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.services.resident_protocol import (
    RESIDENT_CERTIFICATE_HEADER,
    ResidentProtocolError,
    ResidentRuntimeCertificate,
    encoded_public_key,
    issue_runtime_certificate,
    signed_resident_request_headers,
    verify_resident_request,
)

NOW = 1_784_544_000
ACTOR_ID = "actor-123"
HEARTH_ID = "hearth:actor-123"
AUDIENCE = "ww_alderbank"
SCOPE = "session.act"


def _fixture():
    identity_private = Ed25519PrivateKey.generate()
    runtime_private = Ed25519PrivateKey.generate()
    certificate = issue_runtime_certificate(
        identity_private_key=identity_private,
        runtime_public_key=runtime_private.public_key(),
        actor_id=ACTOR_ID,
        hearth_shard_id=HEARTH_ID,
        runtime_generation=3,
        audience=AUDIENCE,
        scopes=["session.travel", SCOPE],
        issued_at=NOW - 60,
        expires_at=NOW + 3600,
        certificate_id="certificate-123",
    )
    body = json.dumps({"session_id": "resident-session", "message": "hello"}, separators=(",", ":")).encode()
    headers = signed_resident_request_headers(
        runtime_private_key=runtime_private,
        certificate=certificate,
        method="POST",
        target="/api/world/location/Commons/chat",
        body=body,
        timestamp=NOW,
        nonce="nonce-123",
    )
    return identity_private, runtime_private, certificate, body, headers


def _verify(identity_private, original_body, headers, **overrides):
    values = {
        "identity_public_key": encoded_public_key(identity_private.public_key()),
        "expected_actor_id": ACTOR_ID,
        "expected_runtime_generation": 3,
        "expected_audience": AUDIENCE,
        "required_scope": SCOPE,
        "method": "POST",
        "target": "/api/world/location/Commons/chat",
        "body": original_body,
        "headers": headers,
        "now": NOW,
    }
    values.update(overrides)
    return verify_resident_request(**values)


def test_certificate_and_exact_request_verify_to_narrow_actor_context():
    identity_private, _runtime_private, _certificate, body, headers = _fixture()

    verified = _verify(identity_private, body, headers)

    assert verified.actor_id == ACTOR_ID
    assert verified.runtime_generation == 3
    assert verified.audience == AUDIENCE
    assert verified.scope == SCOPE
    assert verified.certificate_id == "certificate-123"
    assert verified.nonce == "nonce-123"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"expected_actor_id": "actor-other"}, "actor"),
        ({"expected_runtime_generation": 2}, "generation"),
        ({"expected_runtime_generation": 4}, "generation"),
        ({"expected_audience": "ww_portland"}, "audience"),
        ({"required_scope": "session.bootstrap"}, "scope"),
    ],
)
def test_certificate_rejects_wrong_actor_generation_audience_or_scope(override, message):
    identity_private, _runtime_private, _certificate, body, headers = _fixture()

    with pytest.raises(ResidentProtocolError, match=message):
        _verify(identity_private, body, headers, **override)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"method": "DELETE"}, "signature"),
        ({"target": "/api/session/leave"}, "signature"),
        ({"body": b'{"session_id":"someone-else"}'}, "signature"),
    ],
)
def test_request_signature_cannot_move_to_another_method_target_or_body(override, message):
    identity_private, _runtime_private, _certificate, body, headers = _fixture()

    with pytest.raises(ResidentProtocolError, match=message):
        _verify(identity_private, body, headers, **override)


def test_request_rejects_wrong_runtime_key_and_changed_certificate():
    identity_private, _runtime_private, certificate, body, _headers = _fixture()
    wrong_runtime = Ed25519PrivateKey.generate()
    wrong_headers = signed_resident_request_headers(
        runtime_private_key=wrong_runtime,
        certificate=certificate,
        method="POST",
        target="/api/world/location/Commons/chat",
        body=body,
        timestamp=NOW,
        nonce="nonce-123",
    )

    with pytest.raises(ResidentProtocolError, match="signature"):
        _verify(identity_private, body, wrong_headers)

    changed = dict(wrong_headers)
    raw = ResidentRuntimeCertificate.decode_header(changed[RESIDENT_CERTIFICATE_HEADER]).to_dict()
    raw["actor_id"] = "actor-other"
    changed[RESIDENT_CERTIFICATE_HEADER] = ResidentRuntimeCertificate.from_dict(raw).encode_header()
    with pytest.raises(ResidentProtocolError, match="actor"):
        _verify(identity_private, body, changed)


def test_certificate_rejects_wrong_identity_key_expiry_and_excess_lifetime():
    identity_private, runtime_private, certificate, body, headers = _fixture()

    with pytest.raises(ResidentProtocolError, match="identity key"):
        _verify(Ed25519PrivateKey.generate(), body, headers)
    expired_headers = signed_resident_request_headers(
        runtime_private_key=runtime_private,
        certificate=certificate,
        method="POST",
        target="/api/world/location/Commons/chat",
        body=body,
        timestamp=certificate.expires_at + 1,
        nonce="nonce-after-expiry",
    )
    with pytest.raises(ResidentProtocolError, match="expired"):
        _verify(
            identity_private,
            body,
            expired_headers,
            now=certificate.expires_at + 1,
        )
    with pytest.raises(ResidentProtocolError, match="lifetime"):
        issue_runtime_certificate(
            identity_private_key=identity_private,
            runtime_public_key=Ed25519PrivateKey.generate().public_key(),
            actor_id=ACTOR_ID,
            hearth_shard_id=HEARTH_ID,
            runtime_generation=3,
            audience=AUDIENCE,
            scopes=[SCOPE],
            issued_at=NOW,
            expires_at=NOW + 86_401,
        )


def test_request_rejects_missing_headers_old_timestamp_and_tampered_certificate_signature():
    identity_private, _runtime_private, _certificate, body, headers = _fixture()

    missing = dict(headers)
    missing.pop(RESIDENT_CERTIFICATE_HEADER)
    with pytest.raises(ResidentProtocolError, match="incomplete"):
        _verify(identity_private, body, missing)

    with pytest.raises(ResidentProtocolError, match="timestamp"):
        _verify(identity_private, body, headers, now=NOW + 301)

    raw = ResidentRuntimeCertificate.decode_header(headers[RESIDENT_CERTIFICATE_HEADER]).to_dict()
    raw["identity_signature"] = raw["identity_signature"][:-2] + "aa"
    tampered = dict(headers)
    tampered[RESIDENT_CERTIFICATE_HEADER] = ResidentRuntimeCertificate.from_dict(raw).encode_header()
    with pytest.raises(ResidentProtocolError, match="signature"):
        _verify(identity_private, body, tampered)

    malformed = dict(headers)
    malformed[RESIDENT_CERTIFICATE_HEADER] += "!"
    with pytest.raises(ResidentProtocolError, match="base64"):
        _verify(identity_private, body, malformed)


def test_verifier_returns_nonce_for_atomic_replay_consumption_without_storing_it():
    identity_private, _runtime_private, _certificate, body, headers = _fixture()

    first = _verify(identity_private, body, headers)
    second = _verify(identity_private, body, headers)

    assert first.nonce == second.nonce == "nonce-123"
    assert first.certificate_id == second.certificate_id
    # The pure protocol verifier cannot know database state. The HTTP authority
    # layer must atomically reject the second (certificate_id, nonce) pair.
