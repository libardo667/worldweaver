from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import pytest

from src.identity.hearth_manifest import (
    initialize_hearth_manifest,
    load_hearth_manifest,
)
from src.identity.hearth_envelope import (
    encoded_transport_public_key,
    encrypt_hearth_payload,
    transport_key_id,
)
from src.identity.hearth_handoff import (
    HEARTH_HANDOFF_FILENAME,
    create_hearth_handoff_authorization,
    load_hearth_handoff_authorization,
)
from src.identity.hearth_package import (
    HearthPackageError,
    export_encrypted_hearth_transfer,
    export_hearth_package,
    import_encrypted_hearth_transfer,
    classify_hearth_path,
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


def _write_host_files(tmp_path, name, private_key):
    private_path = tmp_path / f"{name}.key"
    private_path.write_text(
        base64.urlsafe_b64encode(private_key.private_bytes_raw())
        .decode("ascii")
        .rstrip("=")
        + "\n",
        encoding="utf-8",
    )
    public_key = encoded_transport_public_key(private_key.public_key())
    descriptor_path = tmp_path / f"{name}.json"
    descriptor_path.write_text(
        json.dumps(
            {
                "schema": "worldweaver.hearth-transport",
                "schema_version": 1,
                "transport_key_id": transport_key_id(public_key),
                "transport_public_key": public_key,
            }
        ),
        encoding="utf-8",
    )
    return private_path, descriptor_path


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
    handoff = load_hearth_handoff_authorization(
        target / HEARTH_HANDOFF_FILENAME,
        identity_descriptor=descriptor,
    )
    assert handoff.to_dict() == export_report["handoff_authorization"]
    assert handoff.destination_generation == 2
    assert classify_hearth_path(HEARTH_HANDOFF_FILENAME)[0] == "host_specific"
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
    home, identity, descriptor, source_host, _source_seal = _sealed_home(tmp_path)
    destination_host = X25519PrivateKey.generate()
    portable = tmp_path / "portable.wwhearth"
    export_hearth_package(home, portable)
    manifest = load_hearth_manifest(home)
    handoff = create_hearth_handoff_authorization(
        manifest,
        identity_descriptor=descriptor,
        identity_private_key=identity,
        source_transport_public_key=source_host.public_key(),
        destination_transport_public_key=destination_host.public_key(),
    )
    payload = build_hearth_transfer_payload(
        portable.read_bytes(),
        manifest=manifest,
        identity_descriptor=descriptor,
        identity_private_key=identity,
        handoff_authorization=handoff,
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


def test_transfer_commands_load_host_keys_from_files(tmp_path):
    home, _identity, descriptor, source_host, _source_seal = _sealed_home(tmp_path)
    destination_host = X25519PrivateKey.generate()
    source_key_path, _source_descriptor_path = _write_host_files(
        tmp_path, "source-host", source_host
    )
    destination_key_path, destination_descriptor_path = _write_host_files(
        tmp_path, "destination-host", destination_host
    )
    package = tmp_path / "resident.wwhearth.transfer"
    target = tmp_path / "received"
    identity_path = home / "identity" / "resident_identity.json"
    script = Path(__file__).resolve().parents[1] / "scripts" / "hearth_package.py"

    exported = subprocess.run(
        [
            sys.executable,
            str(script),
            "export-transfer",
            str(home),
            str(package),
            "--recipient-host",
            str(destination_descriptor_path),
        ],
        env={
            **os.environ,
            "WW_HEARTH_TRANSPORT_PRIVATE_KEY": str(source_key_path),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert exported.returncode == 0, exported.stdout + exported.stderr
    assert '"status": "exported-transfer"' in exported.stdout

    imported = subprocess.run(
        [
            sys.executable,
            str(script),
            "import-transfer",
            str(package),
            str(target),
            "--resident-identity",
            str(identity_path),
        ],
        env={
            **os.environ,
            "WW_HEARTH_TRANSPORT_PRIVATE_KEY": str(destination_key_path),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert imported.returncode == 0, imported.stdout + imported.stderr
    assert '"status": "imported-transfer"' in imported.stdout
    opened = open_sealed_resident_identity_private_key(
        load_resident_key_seal(target / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME),
        identity_descriptor=descriptor,
        recipient_transport_private_key=destination_host,
    )
    assert opened.public_key().public_bytes_raw() == (
        _identity.public_key().public_bytes_raw()
    )
