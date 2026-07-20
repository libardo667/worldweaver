from __future__ import annotations

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import pytest

import src.identity.hearth_remote_activation as remote_activation
from src.identity.hearth_activation import (
    HearthActivationError,
    acquire_hearth_runtime,
    initialize_hearth_activation,
    load_hearth_activation,
)
from src.identity.hearth_handoff import HearthHandoffAuthorization
from src.identity.hearth_manifest import (
    initialize_hearth_manifest,
    load_hearth_manifest,
)
from src.identity.hearth_package import (
    export_encrypted_hearth_transfer,
    import_encrypted_hearth_transfer,
)
from src.identity.hearth_receipt import (
    HEARTH_ACTIVATION_RECEIPT_FILENAME,
    HEARTH_RETIREMENT_RECEIPT_FILENAME,
    HearthReceiptError,
)
from src.identity.hearth_remote_activation import (
    RemoteHearthActivationError,
    activate_destination_hearth,
    retire_source_hearth,
)
from src.identity.host_witness import (
    HostWitnessDescriptor,
    host_witness_key_id,
)
from src.identity.resident_identity import (
    create_resident_identity_descriptor,
    write_resident_identity_descriptor,
)
from src.identity.resident_key_seal import (
    SEALED_RESIDENT_IDENTITY_FILENAME,
    seal_resident_identity_private_key,
    write_resident_key_seal,
)


def _witness(name):
    private_key = Ed25519PrivateKey.generate()
    public_key = (
        base64.urlsafe_b64encode(private_key.public_key().public_bytes_raw())
        .decode("ascii")
        .rstrip("=")
    )
    return (
        HostWitnessDescriptor(
            witness_id=name,
            public_key=public_key,
            key_id=host_witness_key_id(public_key),
        ),
        private_key,
    )


def _transferred_pair(tmp_path):
    source = tmp_path / "source"
    (source / "identity").mkdir(parents=True)
    (source / "identity" / "resident_id.txt").write_text(
        "actor-123\n", encoding="utf-8"
    )
    initialize_hearth_manifest(source)
    initialize_hearth_activation(source)
    identity = Ed25519PrivateKey.generate()
    descriptor = create_resident_identity_descriptor(
        load_hearth_manifest(source),
        identity_private_key=identity,
    )
    write_resident_identity_descriptor(source, descriptor)
    source_transport = X25519PrivateKey.generate()
    destination_transport = X25519PrivateKey.generate()
    write_resident_key_seal(
        source / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME,
        seal_resident_identity_private_key(
            identity,
            identity_descriptor=descriptor,
            recipient_transport_public_key=source_transport.public_key(),
        ),
    )
    (source / "memory").mkdir()
    (source / "memory" / "runtime_ledger.jsonl").write_text(
        '{"event":"continuity"}\n', encoding="utf-8"
    )
    source_witness, source_witness_key = _witness("source-node")
    destination_witness, destination_witness_key = _witness("destination-node")
    package = tmp_path / "resident.wwhearth.transfer"
    report = export_encrypted_hearth_transfer(
        source,
        package,
        source_transport_private_key=source_transport,
        recipient_transport_public_key=destination_transport.public_key(),
        source_witness=source_witness,
        destination_witness=destination_witness,
    )
    destination = tmp_path / "destination"
    import_encrypted_hearth_transfer(
        package,
        destination,
        recipient_transport_private_key=destination_transport,
        expected_resident_identity=descriptor,
    )
    handoff = HearthHandoffAuthorization.from_dict(
        report["handoff_authorization"],
        identity_descriptor=descriptor,
    )
    return (
        source,
        destination,
        handoff,
        source_transport,
        destination_transport,
        source_witness,
        source_witness_key,
        destination_witness,
        destination_witness_key,
    )


def test_remote_handoff_retires_source_before_activating_successor(tmp_path):
    (
        source,
        destination,
        handoff,
        source_transport,
        destination_transport,
        source_witness,
        source_witness_key,
        destination_witness,
        destination_witness_key,
    ) = _transferred_pair(tmp_path)

    retirement = retire_source_hearth(
        source,
        handoff,
        source_transport_public_key=source_transport.public_key(),
        source_witness=source_witness,
        source_witness_private_key=source_witness_key,
    )
    activation = activate_destination_hearth(
        destination,
        retirement,
        destination_transport_public_key=destination_transport.public_key(),
        source_witness=source_witness,
        destination_witness=destination_witness,
        destination_witness_private_key=destination_witness_key,
    )

    assert retirement.phase == "source_retired"
    assert retirement.runtime_generation == 1
    assert activation.phase == "destination_activated"
    assert activation.runtime_generation == 2
    assert source.is_dir()
    assert (source / "memory" / "runtime_ledger.jsonl").is_file()
    assert load_hearth_activation(source).state == "retired"
    assert load_hearth_manifest(source).runtime_generation == 1
    assert load_hearth_activation(destination).state == "active"
    assert load_hearth_manifest(destination).runtime_generation == 2
    assert (source / HEARTH_RETIREMENT_RECEIPT_FILENAME).is_file()
    assert (destination / HEARTH_RETIREMENT_RECEIPT_FILENAME).is_file()
    assert (destination / HEARTH_ACTIVATION_RECEIPT_FILENAME).is_file()
    with pytest.raises(HearthActivationError, match="retired"):
        acquire_hearth_runtime(source)
    lease = acquire_hearth_runtime(destination)
    lease.release()

    assert (
        retire_source_hearth(
            source,
            handoff,
            source_transport_public_key=source_transport.public_key(),
            source_witness=source_witness,
            source_witness_private_key=source_witness_key,
        )
        == retirement
    )
    assert (
        activate_destination_hearth(
            destination,
            retirement,
            destination_transport_public_key=destination_transport.public_key(),
            source_witness=source_witness,
            destination_witness=destination_witness,
            destination_witness_private_key=destination_witness_key,
        )
        == activation
    )


def test_wrong_source_witness_key_does_not_retire_the_source(tmp_path):
    (
        source,
        _destination,
        handoff,
        source_transport,
        _destination_transport,
        source_witness,
        source_witness_key,
        _destination_witness,
        _destination_witness_key,
    ) = _transferred_pair(tmp_path)

    with pytest.raises(RemoteHearthActivationError, match="private key"):
        retire_source_hearth(
            source,
            handoff,
            source_transport_public_key=source_transport.public_key(),
            source_witness=source_witness,
            source_witness_private_key=Ed25519PrivateKey.generate(),
        )

    assert load_hearth_activation(source).state == "active"
    assert not (source / HEARTH_RETIREMENT_RECEIPT_FILENAME).exists()


def test_receipt_failure_is_restartable_without_reactivating_source(
    tmp_path,
    monkeypatch,
):
    (
        source,
        _destination,
        handoff,
        source_transport,
        _destination_transport,
        source_witness,
        source_witness_key,
        _destination_witness,
        _destination_witness_key,
    ) = _transferred_pair(tmp_path)
    real_create = remote_activation.create_hearth_handoff_receipt

    def fail_receipt(*_args, **_kwargs):
        raise HearthReceiptError("simulated receipt write boundary")

    monkeypatch.setattr(
        remote_activation,
        "create_hearth_handoff_receipt",
        fail_receipt,
    )
    with pytest.raises(RemoteHearthActivationError, match="simulated"):
        retire_source_hearth(
            source,
            handoff,
            source_transport_public_key=source_transport.public_key(),
            source_witness=source_witness,
            source_witness_private_key=source_witness_key,
        )

    assert load_hearth_activation(source).state == "retired"
    assert not (source / HEARTH_RETIREMENT_RECEIPT_FILENAME).exists()
    monkeypatch.setattr(
        remote_activation,
        "create_hearth_handoff_receipt",
        real_create,
    )
    repaired = retire_source_hearth(
        source,
        handoff,
        source_transport_public_key=source_transport.public_key(),
        source_witness=source_witness,
        source_witness_private_key=source_witness_key,
    )
    assert repaired.phase == "source_retired"


def test_destination_receipt_failure_is_restartable_after_safe_activation(
    tmp_path,
    monkeypatch,
):
    (
        source,
        destination,
        handoff,
        source_transport,
        destination_transport,
        source_witness,
        source_witness_key,
        destination_witness,
        destination_witness_key,
    ) = _transferred_pair(tmp_path)
    retirement = retire_source_hearth(
        source,
        handoff,
        source_transport_public_key=source_transport.public_key(),
        source_witness=source_witness,
        source_witness_private_key=source_witness_key,
    )
    real_create = remote_activation.create_hearth_handoff_receipt

    def fail_receipt(*_args, **_kwargs):
        raise HearthReceiptError("simulated activation receipt boundary")

    monkeypatch.setattr(
        remote_activation,
        "create_hearth_handoff_receipt",
        fail_receipt,
    )
    with pytest.raises(RemoteHearthActivationError, match="simulated"):
        activate_destination_hearth(
            destination,
            retirement,
            destination_transport_public_key=destination_transport.public_key(),
            source_witness=source_witness,
            destination_witness=destination_witness,
            destination_witness_private_key=destination_witness_key,
        )

    assert load_hearth_activation(source).state == "retired"
    assert load_hearth_activation(destination).state == "active"
    assert load_hearth_manifest(destination).runtime_generation == 2
    assert not (destination / HEARTH_ACTIVATION_RECEIPT_FILENAME).exists()
    monkeypatch.setattr(
        remote_activation,
        "create_hearth_handoff_receipt",
        real_create,
    )
    repaired = activate_destination_hearth(
        destination,
        retirement,
        destination_transport_public_key=destination_transport.public_key(),
        source_witness=source_witness,
        destination_witness=destination_witness,
        destination_witness_private_key=destination_witness_key,
    )
    assert repaired.phase == "destination_activated"


def test_destination_refuses_wrong_host_or_witness_before_advancing(tmp_path):
    (
        source,
        destination,
        handoff,
        source_transport,
        _destination_transport,
        source_witness,
        source_witness_key,
        destination_witness,
        destination_witness_key,
    ) = _transferred_pair(tmp_path)
    retirement = retire_source_hearth(
        source,
        handoff,
        source_transport_public_key=source_transport.public_key(),
        source_witness=source_witness,
        source_witness_private_key=source_witness_key,
    )

    with pytest.raises(RemoteHearthActivationError, match="destination host"):
        activate_destination_hearth(
            destination,
            retirement,
            destination_transport_public_key=X25519PrivateKey.generate().public_key(),
            source_witness=source_witness,
            destination_witness=destination_witness,
            destination_witness_private_key=destination_witness_key,
        )

    assert load_hearth_manifest(destination).runtime_generation == 1
    assert not (destination / "hearth_activation.json").exists()


def test_destination_refuses_an_already_active_source_generation_without_advancing(
    tmp_path,
):
    (
        source,
        destination,
        handoff,
        source_transport,
        destination_transport,
        source_witness,
        source_witness_key,
        destination_witness,
        destination_witness_key,
    ) = _transferred_pair(tmp_path)
    initialize_hearth_activation(destination)
    retirement = retire_source_hearth(
        source,
        handoff,
        source_transport_public_key=source_transport.public_key(),
        source_witness=source_witness,
        source_witness_private_key=source_witness_key,
    )

    with pytest.raises(RemoteHearthActivationError, match="must still be dormant"):
        activate_destination_hearth(
            destination,
            retirement,
            destination_transport_public_key=destination_transport.public_key(),
            source_witness=source_witness,
            destination_witness=destination_witness,
            destination_witness_private_key=destination_witness_key,
        )

    assert load_hearth_manifest(destination).runtime_generation == 1
    assert load_hearth_activation(destination).state == "active"
