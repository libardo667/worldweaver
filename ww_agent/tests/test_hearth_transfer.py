from __future__ import annotations

import io
import json
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import pytest

from src.identity.hearth_manifest import (
    initialize_hearth_manifest,
    load_hearth_manifest,
)
from src.identity.hearth_envelope import encrypt_hearth_payload
from src.identity.hearth_package import (
    HearthPackageError,
    export_encrypted_hearth_transfer,
    export_hearth_package,
    import_encrypted_hearth_transfer,
)
from src.identity.hearth_transfer import (
    HEARTH_TRANSFER_IDENTITY_KEY,
    build_hearth_transfer_payload,
)
from src.identity.resident_identity import (
    create_resident_identity_descriptor,
    write_resident_identity_descriptor,
)
from src.identity.resident_key_seal import (
    SEALED_RESIDENT_IDENTITY_FILENAME,
    load_resident_key_seal,
    open_sealed_resident_identity_private_key,
    seal_resident_identity_private_key,
    write_resident_key_seal,
)


def _sealed_home(tmp_path):
    home = tmp_path / "source"
    (home / "identity").mkdir(parents=True)
    (home / "identity" / "resident_id.txt").write_text("actor-123\n", encoding="utf-8")
    initialize_hearth_manifest(home)
    identity_private = Ed25519PrivateKey.generate()
    descriptor = create_resident_identity_descriptor(
        load_hearth_manifest(home),
        identity_private_key=identity_private,
    )
    write_resident_identity_descriptor(home, descriptor)
    source_host = X25519PrivateKey.generate()
    source_seal = seal_resident_identity_private_key(
        identity_private,
        identity_descriptor=descriptor,
        recipient_transport_public_key=source_host.public_key(),
    )
    write_resident_key_seal(
        home / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME,
        source_seal,
    )
    (home / "memory").mkdir()
    (home / "memory" / "runtime_ledger.jsonl").write_text(
        '{"event":"private continuity"}\n', encoding="utf-8"
    )
    (home / "workshop").mkdir()
    (home / "workshop" / "carved-cup.txt").write_text(
        "resident artifact\n", encoding="utf-8"
    )
    return home, identity_private, descriptor, source_host, source_seal


def test_transfer_reseals_identity_for_destination_and_keeps_home_dormant(tmp_path):
    home, identity_private, descriptor, source_host, source_seal = _sealed_home(
        tmp_path
    )
    destination_host = X25519PrivateKey.generate()
    package = tmp_path / "resident.wwhearth.transfer"

    export_report = export_encrypted_hearth_transfer(
        home,
        package,
        source_transport_private_key=source_host,
        recipient_transport_public_key=destination_host.public_key(),
    )

    encrypted = package.read_bytes()
    assert b"private continuity" not in encrypted
    assert b"resident artifact" not in encrypted
    assert identity_private.private_bytes_raw() not in encrypted

    target = tmp_path / "destination"
    import_report = import_encrypted_hearth_transfer(
        package,
        target,
        recipient_transport_private_key=destination_host,
        expected_resident_identity=descriptor,
    )

    assert import_report == export_report
    assert (target / "memory" / "runtime_ledger.jsonl").is_file()
    assert (target / "workshop" / "carved-cup.txt").read_text() == (
        "resident artifact\n"
    )
    assert not (target / "hearth_activation.json").exists()
    destination_seal = load_resident_key_seal(
        target / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME
    )
    assert destination_seal != source_seal
    opened = open_sealed_resident_identity_private_key(
        destination_seal,
        identity_descriptor=descriptor,
        recipient_transport_private_key=destination_host,
    )
    assert opened.private_bytes_raw() == identity_private.private_bytes_raw()
    assert (
        load_resident_key_seal(home / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME)
        == source_seal
    )

    plaintext = tmp_path / "portable.wwhearth"
    export_hearth_package(home, plaintext)
    assert SEALED_RESIDENT_IDENTITY_FILENAME.encode() not in plaintext.read_bytes()


def test_transfer_export_requires_the_source_host_key(tmp_path):
    home, _identity, _descriptor, _source_host, _source_seal = _sealed_home(tmp_path)

    with pytest.raises(HearthPackageError, match="another hearth host"):
        export_encrypted_hearth_transfer(
            home,
            tmp_path / "rejected.wwhearth.transfer",
            source_transport_private_key=X25519PrivateKey.generate(),
            recipient_transport_public_key=X25519PrivateKey.generate().public_key(),
        )

    assert not (tmp_path / "rejected.wwhearth.transfer").exists()


def test_transfer_import_rejects_wrong_host_card_and_tampering_without_a_home(
    tmp_path,
):
    home, _identity, descriptor, source_host, _source_seal = _sealed_home(tmp_path)
    destination_host = X25519PrivateKey.generate()
    package = tmp_path / "resident.wwhearth.transfer"
    export_encrypted_hearth_transfer(
        home,
        package,
        source_transport_private_key=source_host,
        recipient_transport_public_key=destination_host.public_key(),
    )

    wrong_host_target = tmp_path / "wrong-host"
    with pytest.raises(HearthPackageError, match="another host"):
        import_encrypted_hearth_transfer(
            package,
            wrong_host_target,
            recipient_transport_private_key=X25519PrivateKey.generate(),
            expected_resident_identity=descriptor,
        )
    assert not wrong_host_target.exists()

    other_home = tmp_path / "other"
    (other_home / "identity").mkdir(parents=True)
    (other_home / "identity" / "resident_id.txt").write_text(
        "actor-other\n", encoding="utf-8"
    )
    initialize_hearth_manifest(other_home)
    other_identity = Ed25519PrivateKey.generate()
    other_descriptor = create_resident_identity_descriptor(
        load_hearth_manifest(other_home),
        identity_private_key=other_identity,
    )
    wrong_card_target = tmp_path / "wrong-card"
    with pytest.raises(HearthPackageError, match="identity"):
        import_encrypted_hearth_transfer(
            package,
            wrong_card_target,
            recipient_transport_private_key=destination_host,
            expected_resident_identity=other_descriptor,
        )
    assert not wrong_card_target.exists()

    tampered = json.loads(package.read_bytes())
    ciphertext = tampered["ciphertext"]
    tampered["ciphertext"] = ("A" if ciphertext[0] != "A" else "B") + ciphertext[1:]
    tampered_package = tmp_path / "tampered.wwhearth.transfer"
    tampered_package.write_text(json.dumps(tampered), encoding="utf-8")
    tampered_target = tmp_path / "tampered"
    with pytest.raises(HearthPackageError, match="signature|authenticated"):
        import_encrypted_hearth_transfer(
            tampered_package,
            tampered_target,
            recipient_transport_private_key=destination_host,
            expected_resident_identity=descriptor,
        )
    assert not tampered_target.exists()


def test_transfer_rejects_a_signed_payload_with_the_wrong_inner_identity_key(tmp_path):
    home, identity, descriptor, _source_host, _source_seal = _sealed_home(tmp_path)
    destination_host = X25519PrivateKey.generate()
    portable = tmp_path / "portable.wwhearth"
    export_hearth_package(home, portable)
    manifest = load_hearth_manifest(home)
    payload = build_hearth_transfer_payload(
        portable.read_bytes(),
        manifest=manifest,
        identity_descriptor=descriptor,
        identity_private_key=identity,
    )
    with zipfile.ZipFile(io.BytesIO(payload), "r") as source:
        members = {name: source.read(name) for name in source.namelist()}
    members[HEARTH_TRANSFER_IDENTITY_KEY] = (
        Ed25519PrivateKey.generate().private_bytes_raw()
    )
    corrupted = io.BytesIO()
    with zipfile.ZipFile(corrupted, "w") as transfer:
        for name, content in members.items():
            transfer.writestr(name, content)
    package = tmp_path / "wrong-inner-key.wwhearth.transfer"
    package.write_bytes(
        encrypt_hearth_payload(
            corrupted.getvalue(),
            actor_id=manifest.actor_id,
            hearth_shard_id=manifest.hearth_shard_id,
            runtime_generation=manifest.runtime_generation,
            resident_identity_private_key=identity,
            recipient_transport_public_key=destination_host.public_key(),
        )
    )
    target = tmp_path / "rejected-inner-key"

    with pytest.raises(HearthPackageError, match="key does not match"):
        import_encrypted_hearth_transfer(
            package,
            target,
            recipient_transport_private_key=destination_host,
            expected_resident_identity=descriptor,
        )

    assert not target.exists()
