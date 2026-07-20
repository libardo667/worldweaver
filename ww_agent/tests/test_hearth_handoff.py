from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import pytest

from src.identity.hearth_handoff import (
    HearthHandoffAuthorization,
    HearthHandoffError,
    create_hearth_handoff_authorization,
)
from src.identity.hearth_envelope import transport_key_id
from src.identity.hearth_manifest import HearthManifest
from src.identity.resident_identity import create_resident_identity_descriptor


def _handoff():
    manifest = HearthManifest(
        actor_id="actor-123",
        hearth_shard_id="hearth:actor-123",
        runtime_generation=7,
    )
    identity = Ed25519PrivateKey.generate()
    descriptor = create_resident_identity_descriptor(
        manifest,
        identity_private_key=identity,
    )
    source_host = X25519PrivateKey.generate()
    destination_host = X25519PrivateKey.generate()
    authorization = create_hearth_handoff_authorization(
        manifest,
        identity_descriptor=descriptor,
        identity_private_key=identity,
        source_transport_public_key=source_host.public_key(),
        destination_transport_public_key=destination_host.public_key(),
    )
    return authorization, descriptor, source_host, destination_host


def test_resident_authorizes_one_host_and_generation_transition():
    authorization, descriptor, source_host, destination_host = _handoff()

    verified = HearthHandoffAuthorization.from_dict(
        authorization.to_dict(),
        identity_descriptor=descriptor,
    )

    assert verified == authorization
    assert verified.source_generation == 7
    assert verified.destination_generation == 8
    assert verified.source_host_key_id != verified.destination_host_key_id
    assert verified.source_host_key_id == transport_key_id(source_host.public_key())
    assert verified.destination_host_key_id == transport_key_id(
        destination_host.public_key()
    )
    assert source_host.private_bytes_raw() != destination_host.private_bytes_raw()


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("actor_id", "other-actor", "identity card"),
        ("destination_generation", 9, "exactly one"),
        ("destination_host_key_id", "x25519:" + "0" * 32, "signature"),
        ("resident_signature", "A" * 86, "signature"),
    ],
)
def test_handoff_rejects_changed_identity_generation_host_or_signature(
    field, replacement, message
):
    authorization, descriptor, _source_host, _destination_host = _handoff()
    raw = authorization.to_dict()
    raw[field] = replacement

    with pytest.raises(HearthHandoffError, match=message):
        HearthHandoffAuthorization.from_dict(
            raw,
            identity_descriptor=descriptor,
        )


def test_handoff_rejects_the_same_source_and_destination_host():
    manifest = HearthManifest(
        actor_id="actor-123",
        hearth_shard_id="hearth:actor-123",
    )
    identity = Ed25519PrivateKey.generate()
    descriptor = create_resident_identity_descriptor(
        manifest,
        identity_private_key=identity,
    )
    host = X25519PrivateKey.generate()

    with pytest.raises(HearthHandoffError, match="host binding"):
        create_hearth_handoff_authorization(
            manifest,
            identity_descriptor=descriptor,
            identity_private_key=identity,
            source_transport_public_key=host.public_key(),
            destination_transport_public_key=host.public_key(),
        )
