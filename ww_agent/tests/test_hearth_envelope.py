from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import pytest

from src.identity.hearth_envelope import (
    HearthEnvelopeError,
    decrypt_hearth_payload,
    encoded_resident_identity_public_key,
    encrypt_hearth_payload,
    transport_key_id,
)


def _keys():
    return Ed25519PrivateKey.generate(), X25519PrivateKey.generate()


def _envelope(payload=b"stopped portable hearth payload"):
    identity, host = _keys()
    encoded = encrypt_hearth_payload(
        payload,
        actor_id="actor-123",
        hearth_shard_id="hearth:actor-123",
        runtime_generation=4,
        resident_identity_private_key=identity,
        recipient_transport_public_key=host.public_key(),
    )
    return identity, host, encoded


def _decode_urlsafe(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _encode_urlsafe(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def test_envelope_round_trip_binds_resident_generation_and_destination_host():
    payload = b"private stopped hearth\x00payload"
    identity, host, encoded = _envelope(payload)

    opened = decrypt_hearth_payload(
        encoded,
        recipient_transport_private_key=host,
        expected_resident_identity_public_key=encoded_resident_identity_public_key(
            identity.public_key()
        ),
    )

    assert opened.payload == payload
    assert opened.actor_id == "actor-123"
    assert opened.hearth_shard_id == "hearth:actor-123"
    assert opened.runtime_generation == 4
    assert opened.recipient_key_id == transport_key_id(host.public_key())
    assert payload not in encoded


def test_wrong_host_and_wrong_expected_resident_are_rejected():
    identity, _host, encoded = _envelope()

    with pytest.raises(HearthEnvelopeError, match="another host"):
        decrypt_hearth_payload(
            encoded,
            recipient_transport_private_key=X25519PrivateKey.generate(),
            expected_resident_identity_public_key=encoded_resident_identity_public_key(
                identity.public_key()
            ),
        )
    with pytest.raises(HearthEnvelopeError, match="expected identity"):
        decrypt_hearth_payload(
            encoded,
            recipient_transport_private_key=_host,
            expected_resident_identity_public_key=encoded_resident_identity_public_key(
                Ed25519PrivateKey.generate().public_key()
            ),
        )


@pytest.mark.parametrize("field", ["actor_id", "runtime_generation", "nonce"])
def test_signed_header_tampering_is_rejected(field):
    identity, host, encoded = _envelope()
    raw = json.loads(encoded)
    raw[field] = (
        "actor-other"
        if field == "actor_id"
        else (5 if field == "runtime_generation" else _encode_urlsafe(b"0" * 12))
    )

    with pytest.raises(HearthEnvelopeError, match="signature"):
        decrypt_hearth_payload(
            (json.dumps(raw) + "\n").encode(),
            recipient_transport_private_key=host,
            expected_resident_identity_public_key=encoded_resident_identity_public_key(
                identity.public_key()
            ),
        )


def test_ciphertext_and_signature_tampering_are_rejected():
    identity, host, encoded = _envelope()
    expected_identity = encoded_resident_identity_public_key(identity.public_key())
    raw = json.loads(encoded)
    ciphertext = bytearray(_decode_urlsafe(raw["ciphertext"]))
    ciphertext[-1] ^= 1
    raw["ciphertext"] = _encode_urlsafe(bytes(ciphertext))
    with pytest.raises(HearthEnvelopeError, match="signature"):
        decrypt_hearth_payload(
            json.dumps(raw).encode(),
            recipient_transport_private_key=host,
            expected_resident_identity_public_key=expected_identity,
        )


def test_valid_resident_signature_cannot_hide_broken_ciphertext():
    identity, host, encoded = _envelope()
    expected_identity = encoded_resident_identity_public_key(identity.public_key())
    raw = json.loads(encoded)
    ciphertext = bytearray(_decode_urlsafe(raw["ciphertext"]))
    ciphertext[-1] ^= 1
    raw["ciphertext"] = _encode_urlsafe(bytes(ciphertext))
    signed = {key: value for key, value in raw.items() if key != "resident_signature"}
    canonical = json.dumps(
        signed,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    raw["resident_signature"] = _encode_urlsafe(identity.sign(canonical))

    with pytest.raises(HearthEnvelopeError, match="ciphertext"):
        decrypt_hearth_payload(
            json.dumps(raw).encode(),
            recipient_transport_private_key=host,
            expected_resident_identity_public_key=expected_identity,
        )

    raw = json.loads(encoded)
    signature = bytearray(_decode_urlsafe(raw["resident_signature"]))
    signature[-1] ^= 1
    raw["resident_signature"] = _encode_urlsafe(bytes(signature))
    with pytest.raises(HearthEnvelopeError, match="signature"):
        decrypt_hearth_payload(
            json.dumps(raw).encode(),
            recipient_transport_private_key=host,
            expected_resident_identity_public_key=expected_identity,
        )


def test_envelope_is_randomized_and_strict_about_its_versioned_fields():
    identity, host = _keys()
    kwargs = {
        "actor_id": "actor-123",
        "hearth_shard_id": "hearth:actor-123",
        "runtime_generation": 1,
        "resident_identity_private_key": identity,
        "recipient_transport_public_key": host.public_key(),
    }
    first = encrypt_hearth_payload(b"same", **kwargs)
    second = encrypt_hearth_payload(b"same", **kwargs)
    assert first != second

    raw = json.loads(first)
    raw["unexpected"] = True
    with pytest.raises(HearthEnvelopeError, match="fields"):
        decrypt_hearth_payload(
            json.dumps(raw).encode(),
            recipient_transport_private_key=host,
            expected_resident_identity_public_key=encoded_resident_identity_public_key(
                identity.public_key()
            ),
        )
