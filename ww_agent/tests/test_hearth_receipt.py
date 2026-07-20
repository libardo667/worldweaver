from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import pytest

from src.identity.hearth_handoff import create_hearth_handoff_authorization
from src.identity.hearth_manifest import HearthManifest
from src.identity.hearth_receipt import (
    HearthHandoffReceipt,
    HearthReceiptError,
    create_hearth_handoff_receipt,
    load_hearth_handoff_receipt,
    write_hearth_handoff_receipt,
)
from src.identity.host_witness import (
    HostWitnessDescriptor,
    HostWitnessError,
    host_witness_key_id,
    load_host_witness_private_key,
)
from src.identity.resident_identity import create_resident_identity_descriptor


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


def _handoff():
    manifest = HearthManifest(
        actor_id="actor-123",
        hearth_shard_id="hearth:actor-123",
        runtime_generation=4,
    )
    identity = Ed25519PrivateKey.generate()
    descriptor = create_resident_identity_descriptor(
        manifest,
        identity_private_key=identity,
    )
    source_witness, source_key = _witness("source-node")
    destination_witness, destination_key = _witness("destination-node")
    authorization = create_hearth_handoff_authorization(
        manifest,
        identity_descriptor=descriptor,
        identity_private_key=identity,
        source_transport_public_key=X25519PrivateKey.generate().public_key(),
        destination_transport_public_key=X25519PrivateKey.generate().public_key(),
        source_witness_id=source_witness.witness_id,
        source_witness_public_key=source_witness.public_key_object,
        destination_witness_id=destination_witness.witness_id,
        destination_witness_public_key=destination_witness.public_key_object,
    )
    return (
        authorization,
        source_witness,
        source_key,
        destination_witness,
        destination_key,
    )


def test_source_and_destination_receipts_have_distinct_witnesses_and_generations():
    handoff, source, source_key, destination, destination_key = _handoff()

    retired = create_hearth_handoff_receipt(
        handoff,
        phase="source_retired",
        witness=source,
        witness_private_key=source_key,
    )
    activated = create_hearth_handoff_receipt(
        handoff,
        phase="destination_activated",
        witness=destination,
        witness_private_key=destination_key,
    )

    assert retired.runtime_generation == 4
    assert retired.witness_id == "source-node"
    assert activated.runtime_generation == 5
    assert activated.witness_id == "destination-node"
    assert retired.witness_signature != activated.witness_signature


def test_receipt_rejects_wrong_witness_key_phase_and_tampering():
    handoff, source, source_key, destination, _destination_key = _handoff()
    receipt = create_hearth_handoff_receipt(
        handoff,
        phase="source_retired",
        witness=source,
        witness_private_key=source_key,
    )

    with pytest.raises(HearthReceiptError, match="not authorized"):
        HearthHandoffReceipt.from_dict(
            receipt.to_dict(),
            handoff=handoff,
            witness=destination,
        )
    with pytest.raises(HearthReceiptError, match="private key"):
        create_hearth_handoff_receipt(
            handoff,
            phase="source_retired",
            witness=source,
            witness_private_key=Ed25519PrivateKey.generate(),
        )
    changed_phase = receipt.to_dict()
    changed_phase["phase"] = "destination_activated"
    with pytest.raises(HearthReceiptError, match="authorized handoff|witness"):
        HearthHandoffReceipt.from_dict(
            changed_phase,
            handoff=handoff,
            witness=source,
        )
    tampered = receipt.to_dict()
    tampered["runtime_generation"] = 99
    with pytest.raises(HearthReceiptError, match="authorized handoff"):
        HearthHandoffReceipt.from_dict(
            tampered,
            handoff=handoff,
            witness=source,
        )


def test_receipt_file_is_owner_only_and_never_replaced(tmp_path):
    handoff, source, source_key, _destination, _destination_key = _handoff()
    receipt = create_hearth_handoff_receipt(
        handoff,
        phase="source_retired",
        witness=source,
        witness_private_key=source_key,
    )
    path = tmp_path / "retirement.json"

    write_hearth_handoff_receipt(
        path,
        receipt,
        handoff=handoff,
        witness=source,
    )

    assert path.stat().st_mode & 0o077 == 0
    assert (
        load_hearth_handoff_receipt(
            path,
            handoff=handoff,
            witness=source,
        )
        == receipt
    )
    with pytest.raises(HearthReceiptError, match="Refusing to replace"):
        write_hearth_handoff_receipt(
            path,
            receipt,
            handoff=handoff,
            witness=source,
        )


def test_node_descriptor_loader_contract_rejects_extra_fields():
    _witness_descriptor, key = _witness("source-node")
    public_key = (
        base64.urlsafe_b64encode(key.public_key().public_bytes_raw())
        .decode("ascii")
        .rstrip("=")
    )
    raw = {
        "schema": "worldweaver.node",
        "schema_version": 1,
        "node_id": "source-node",
        "shard_type": "city",
        "city_id": "source",
        "public_key": public_key,
        "owner": "nobody",
    }

    with pytest.raises(HostWitnessError, match="unexpected fields"):
        HostWitnessDescriptor.from_node_descriptor(json.loads(json.dumps(raw)))


def test_witness_key_loader_refuses_links(tmp_path):
    _witness_descriptor, private_key = _witness("source-node")
    path = tmp_path / "node.key"
    path.write_text(
        base64.urlsafe_b64encode(private_key.private_bytes_raw())
        .decode("ascii")
        .rstrip("=")
        + "\n",
        encoding="utf-8",
    )

    assert load_host_witness_private_key(path).private_bytes_raw() == (
        private_key.private_bytes_raw()
    )
    linked = tmp_path / "linked.key"
    linked.symlink_to(path)
    with pytest.raises(HostWitnessError, match="missing or unsafe"):
        load_host_witness_private_key(linked)
