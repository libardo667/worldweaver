from __future__ import annotations

import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import pytest

from src.identity.hearth_manifest import HearthManifest
from src.identity.hearth_package import classify_hearth_path
from src.identity.resident_identity import create_resident_identity_descriptor
from src.identity.resident_key_seal import (
    ResidentKeySealError,
    load_resident_key_seal,
    open_sealed_resident_identity_private_key,
    seal_resident_identity_private_key,
    write_resident_key_seal,
)


def _identity():
    private_key = Ed25519PrivateKey.generate()
    descriptor = create_resident_identity_descriptor(
        HearthManifest(actor_id="actor-123", hearth_shard_id="hearth:actor-123"),
        identity_private_key=private_key,
    )
    return private_key, descriptor


def test_resident_identity_key_is_sealed_for_one_host_and_card(tmp_path):
    identity_private, descriptor = _identity()
    host_private = X25519PrivateKey.generate()

    sealed = seal_resident_identity_private_key(
        identity_private,
        identity_descriptor=descriptor,
        recipient_transport_public_key=host_private.public_key(),
    )
    path = tmp_path / "identity" / "resident_identity.sealed.json"
    path.parent.mkdir()
    write_resident_key_seal(path, sealed)
    opened = open_sealed_resident_identity_private_key(
        load_resident_key_seal(path),
        identity_descriptor=descriptor,
        recipient_transport_private_key=host_private,
    )

    assert path.stat().st_mode & 0o077 == 0
    assert opened.private_bytes_raw() == identity_private.private_bytes_raw()
    assert identity_private.private_bytes_raw() not in path.read_bytes()
    assert (
        classify_hearth_path("identity/resident_identity.sealed.json")[0]
        == "host_specific"
    )


def test_seal_rejects_wrong_host_card_key_and_tampering(tmp_path):
    identity_private, descriptor = _identity()
    other_private, other_descriptor = _identity()
    host_private = X25519PrivateKey.generate()
    sealed = seal_resident_identity_private_key(
        identity_private,
        identity_descriptor=descriptor,
        recipient_transport_public_key=host_private.public_key(),
    )

    with pytest.raises(ResidentKeySealError, match="another hearth host"):
        open_sealed_resident_identity_private_key(
            sealed,
            identity_descriptor=descriptor,
            recipient_transport_private_key=X25519PrivateKey.generate(),
        )
    with pytest.raises(ResidentKeySealError, match="public identity card"):
        open_sealed_resident_identity_private_key(
            sealed,
            identity_descriptor=other_descriptor,
            recipient_transport_private_key=host_private,
        )
    with pytest.raises(ResidentKeySealError, match="does not match"):
        seal_resident_identity_private_key(
            other_private,
            identity_descriptor=descriptor,
            recipient_transport_public_key=host_private.public_key(),
        )

    tampered = json.loads(sealed)
    ciphertext = tampered["ciphertext"]
    tampered["ciphertext"] = ("A" if ciphertext[0] != "A" else "B") + ciphertext[1:]
    with pytest.raises(ResidentKeySealError, match="authenticated"):
        open_sealed_resident_identity_private_key(
            (json.dumps(tampered) + "\n").encode(),
            identity_descriptor=descriptor,
            recipient_transport_private_key=host_private,
        )

    path = tmp_path / "identity" / "resident_identity.sealed.json"
    path.parent.mkdir()
    write_resident_key_seal(path, sealed)
    with pytest.raises(ResidentKeySealError, match="Refusing to replace"):
        write_resident_key_seal(path, sealed)


def test_seal_is_randomized_for_the_same_identity_and_host():
    identity_private, descriptor = _identity()
    host_private = X25519PrivateKey.generate()

    first = seal_resident_identity_private_key(
        identity_private,
        identity_descriptor=descriptor,
        recipient_transport_public_key=host_private.public_key(),
    )
    second = seal_resident_identity_private_key(
        identity_private,
        identity_descriptor=descriptor,
        recipient_transport_public_key=host_private.public_key(),
    )

    assert first != second
