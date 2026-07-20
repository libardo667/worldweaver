from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from src.identity.hearth_manifest import HearthManifest, initialize_hearth_manifest
from src.identity.hearth_package import classify_hearth_path
from src.identity.resident_identity import (
    ResidentIdentityDescriptor,
    ResidentIdentityError,
    create_resident_identity_descriptor,
    load_resident_identity_descriptor,
    resident_identity_key_id,
    write_resident_identity_descriptor,
)


def _home(tmp_path):
    home = tmp_path / "resident"
    (home / "identity").mkdir(parents=True)
    (home / "identity" / "resident_id.txt").write_text("actor-123\n", encoding="utf-8")
    manifest = initialize_hearth_manifest(home)
    return home, manifest


def test_public_descriptor_round_trip_is_self_signed_and_portable(tmp_path):
    home, manifest = _home(tmp_path)
    identity = Ed25519PrivateKey.generate()
    descriptor = create_resident_identity_descriptor(
        manifest,
        identity_private_key=identity,
    )

    write_resident_identity_descriptor(home, descriptor)
    loaded = load_resident_identity_descriptor(home)

    assert loaded == descriptor
    assert loaded.actor_id == manifest.actor_id
    assert loaded.hearth_shard_id == manifest.hearth_shard_id
    assert loaded.identity_key_id == resident_identity_key_id(identity.public_key())
    assert classify_hearth_path("identity/resident_identity.json")[0] == "portable"
    assert set(loaded.to_dict()) == {
        "schema",
        "schema_version",
        "actor_id",
        "hearth_shard_id",
        "identity_public_key",
        "identity_key_id",
        "recovery_policy_version",
        "identity_signature",
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", True, "schema"),
        ("actor_id", " actor-123", "actor ID"),
        ("actor_id", "actor-456", "hearth shard ID"),
        ("hearth_shard_id", "hearth:actor-456", "hearth shard ID"),
        ("identity_key_id", "ed25519:" + ("0" * 32), "key ID"),
        ("recovery_policy_version", 2, "signature"),
    ],
)
def test_descriptor_rejects_changed_signed_fields(field, value, message):
    identity = Ed25519PrivateKey.generate()
    descriptor = create_resident_identity_descriptor(
        HearthManifest(actor_id="actor-123", hearth_shard_id="hearth:actor-123"),
        identity_private_key=identity,
    )
    raw = descriptor.to_dict()
    raw[field] = value

    with pytest.raises(ResidentIdentityError, match=message):
        ResidentIdentityDescriptor.from_dict(raw)


def test_descriptor_rejects_signature_from_another_key():
    first = create_resident_identity_descriptor(
        HearthManifest(actor_id="actor-123", hearth_shard_id="hearth:actor-123"),
        identity_private_key=Ed25519PrivateKey.generate(),
    )
    second = create_resident_identity_descriptor(
        HearthManifest(actor_id="actor-123", hearth_shard_id="hearth:actor-123"),
        identity_private_key=Ed25519PrivateKey.generate(),
    )
    raw = first.to_dict()
    raw["identity_signature"] = second.identity_signature

    with pytest.raises(ResidentIdentityError, match="signature"):
        ResidentIdentityDescriptor.from_dict(raw)


def test_load_checks_manifest_and_write_refuses_replacement(tmp_path):
    home, manifest = _home(tmp_path)
    descriptor = create_resident_identity_descriptor(
        manifest,
        identity_private_key=Ed25519PrivateKey.generate(),
    )
    wrong_home = tmp_path / "other"
    (wrong_home / "identity").mkdir(parents=True)
    (wrong_home / "identity" / "resident_id.txt").write_text(
        "actor-456\n", encoding="utf-8"
    )
    initialize_hearth_manifest(wrong_home)

    with pytest.raises(ResidentIdentityError, match="manifest"):
        write_resident_identity_descriptor(wrong_home, descriptor)

    write_resident_identity_descriptor(home, descriptor)
    with pytest.raises(ResidentIdentityError, match="refusing to replace"):
        write_resident_identity_descriptor(home, descriptor)
