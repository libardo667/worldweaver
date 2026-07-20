from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import pytest

from src.identity.hearth_envelope import (
    encoded_resident_identity_public_key,
    encrypt_hearth_payload,
)
from src.identity.hearth_manifest import initialize_hearth_manifest
from src.identity.hearth_package import (
    HearthPackageError,
    export_encrypted_hearth_package,
    export_hearth_package,
    import_encrypted_hearth_package,
)


def _home(tmp_path):
    home = tmp_path / "resident"
    (home / "identity").mkdir(parents=True)
    (home / "identity" / "resident_id.txt").write_text("actor-123\n", encoding="utf-8")
    initialize_hearth_manifest(home)
    (home / "memory").mkdir()
    (home / "memory" / "runtime_ledger.jsonl").write_text(
        '{"event":"private resident evidence"}\n', encoding="utf-8"
    )
    (home / "workshop").mkdir()
    (home / "workshop" / "note.md").write_text(
        "a private resident note\n", encoding="utf-8"
    )
    return home


def _keys():
    return Ed25519PrivateKey.generate(), X25519PrivateKey.generate()


def test_encrypted_export_import_restores_portable_state_without_plaintext_package(
    tmp_path,
):
    home = _home(tmp_path)
    identity, host = _keys()
    package = tmp_path / "resident.wwhearth.enc"

    export_report = export_encrypted_hearth_package(
        home,
        package,
        resident_identity_private_key=identity,
        recipient_transport_public_key=host.public_key(),
    )

    assert package.is_file()
    assert b"a private resident note" not in package.read_bytes()
    assert not list(tmp_path.glob(".*.tmp"))
    imported = tmp_path / "imported"
    import_report = import_encrypted_hearth_package(
        package,
        imported,
        recipient_transport_private_key=host,
        expected_resident_identity_public_key=encoded_resident_identity_public_key(
            identity.public_key()
        ),
    )

    assert import_report == export_report
    assert (imported / "identity" / "resident_id.txt").read_text() == "actor-123\n"
    assert (imported / "memory" / "runtime_ledger.jsonl").is_file()
    assert (imported / "workshop" / "note.md").read_text() == (
        "a private resident note\n"
    )


def test_encrypted_import_rejects_wrong_host_without_partial_home(tmp_path):
    home = _home(tmp_path)
    identity, host = _keys()
    package = tmp_path / "resident.wwhearth.enc"
    export_encrypted_hearth_package(
        home,
        package,
        resident_identity_private_key=identity,
        recipient_transport_public_key=host.public_key(),
    )
    target = tmp_path / "rejected"

    with pytest.raises(HearthPackageError, match="another host"):
        import_encrypted_hearth_package(
            package,
            target,
            recipient_transport_private_key=X25519PrivateKey.generate(),
            expected_resident_identity_public_key=encoded_resident_identity_public_key(
                identity.public_key()
            ),
        )

    assert not target.exists()
    assert not list(tmp_path.glob(".rejected.import.*"))


@pytest.mark.parametrize(
    ("actor_id", "hearth_shard_id", "runtime_generation"),
    [
        ("different-actor", "hearth:actor-123", 1),
        ("actor-123", "hearth:different-actor", 1),
        ("actor-123", "hearth:actor-123", 2),
    ],
)
def test_encrypted_import_binds_outer_identity_and_generation_to_inner_manifest(
    tmp_path, actor_id, hearth_shard_id, runtime_generation
):
    home = _home(tmp_path)
    plaintext = tmp_path / "inner.wwhearth"
    export_hearth_package(home, plaintext)
    identity, host = _keys()
    mismatched = encrypt_hearth_payload(
        plaintext.read_bytes(),
        actor_id=actor_id,
        hearth_shard_id=hearth_shard_id,
        runtime_generation=runtime_generation,
        resident_identity_private_key=identity,
        recipient_transport_public_key=host.public_key(),
    )
    package = tmp_path / "mismatched.wwhearth.enc"
    package.write_bytes(mismatched)
    target = tmp_path / "rejected"

    with pytest.raises(HearthPackageError, match="inner package"):
        import_encrypted_hearth_package(
            package,
            target,
            recipient_transport_private_key=host,
            expected_resident_identity_public_key=encoded_resident_identity_public_key(
                identity.public_key()
            ),
        )

    assert not target.exists()
