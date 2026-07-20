# SPDX-License-Identifier: AGPL-3.0-or-later
"""Restartable two-host retirement and activation for one hearth handoff.

This module never deletes the retired source. Its receipts are evidence for a
later review, not permission to destroy recovery material.
"""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

from src.identity.hearth_activation import (
    HearthActivation,
    HearthActivationError,
    HearthRuntimeLease,
    activation_path,
    load_hearth_activation,
    write_hearth_activation_locked,
)
from src.identity.hearth_envelope import transport_key_id
from src.identity.hearth_handoff import (
    HEARTH_HANDOFF_FILENAME,
    HearthHandoffAuthorization,
    HearthHandoffError,
    load_hearth_handoff_authorization,
    write_hearth_handoff_authorization,
)
from src.identity.hearth_manifest import (
    HearthManifestError,
    advance_hearth_manifest_generation,
    load_hearth_manifest,
)
from src.identity.hearth_receipt import (
    HEARTH_ACTIVATION_RECEIPT_FILENAME,
    HEARTH_RETIREMENT_RECEIPT_FILENAME,
    HearthHandoffReceipt,
    HearthReceiptError,
    create_hearth_handoff_receipt,
    load_hearth_handoff_receipt,
    write_hearth_handoff_receipt,
)
from src.identity.host_witness import HostWitnessDescriptor
from src.identity.resident_identity import (
    ResidentIdentityDescriptor,
    ResidentIdentityError,
    load_resident_identity_descriptor,
)


class RemoteHearthActivationError(RuntimeError):
    """A cross-host activation step is unsafe, invalid, or out of order."""


def _verified_handoff(
    authorization: HearthHandoffAuthorization,
    descriptor: ResidentIdentityDescriptor,
) -> HearthHandoffAuthorization:
    try:
        return HearthHandoffAuthorization.from_dict(
            authorization.to_dict(),
            identity_descriptor=descriptor,
        )
    except HearthHandoffError as exc:
        raise RemoteHearthActivationError(str(exc)) from exc


def _require_witness_private_key(
    witness: HostWitnessDescriptor,
    private_key: Ed25519PrivateKey,
) -> None:
    if private_key.public_key().public_bytes_raw() != (
        witness.public_key_object.public_bytes_raw()
    ):
        raise RemoteHearthActivationError(
            "host witness private key does not match its public descriptor"
        )


def _ensure_local_handoff(
    home: Path,
    handoff: HearthHandoffAuthorization,
    descriptor: ResidentIdentityDescriptor,
) -> None:
    path = home / HEARTH_HANDOFF_FILENAME
    try:
        if path.exists() or path.is_symlink():
            recorded = load_hearth_handoff_authorization(
                path,
                identity_descriptor=descriptor,
            )
            if recorded != handoff:
                raise RemoteHearthActivationError(
                    "resident home records a different hearth handoff"
                )
            return
        write_hearth_handoff_authorization(
            path,
            handoff,
            identity_descriptor=descriptor,
        )
    except HearthHandoffError as exc:
        raise RemoteHearthActivationError(str(exc)) from exc


def _ensure_receipt(
    path: Path,
    receipt: HearthHandoffReceipt,
    *,
    handoff: HearthHandoffAuthorization,
    witness: HostWitnessDescriptor,
) -> HearthHandoffReceipt:
    try:
        if path.exists() or path.is_symlink():
            recorded = load_hearth_handoff_receipt(
                path,
                handoff=handoff,
                witness=witness,
            )
            if recorded != receipt:
                raise RemoteHearthActivationError(
                    "resident home records a different hearth receipt"
                )
            return recorded
        write_hearth_handoff_receipt(
            path,
            receipt,
            handoff=handoff,
            witness=witness,
        )
        return receipt
    except HearthReceiptError as exc:
        raise RemoteHearthActivationError(str(exc)) from exc


def retire_source_hearth(
    resident_dir: Path,
    authorization: HearthHandoffAuthorization,
    *,
    source_transport_public_key: X25519PublicKey,
    source_witness: HostWitnessDescriptor,
    source_witness_private_key: Ed25519PrivateKey,
) -> HearthHandoffReceipt:
    """Durably retire N, then create its source-witnessed receipt."""

    home = Path(resident_dir)
    try:
        descriptor = load_resident_identity_descriptor(home)
        handoff = _verified_handoff(authorization, descriptor)
        if (
            handoff.source_host_key_id != transport_key_id(source_transport_public_key)
            or handoff.source_witness_id != source_witness.witness_id
            or handoff.source_witness_key_id != source_witness.key_id
        ):
            raise RemoteHearthActivationError(
                "hearth handoff does not authorize this source host"
            )
        _require_witness_private_key(source_witness, source_witness_private_key)
        with HearthRuntimeLease(home):
            manifest = load_hearth_manifest(home)
            if (
                manifest.actor_id != handoff.actor_id
                or manifest.hearth_shard_id != handoff.hearth_shard_id
                or manifest.runtime_generation != handoff.source_generation
            ):
                raise RemoteHearthActivationError(
                    "source hearth does not match the authorized generation"
                )
            activation = load_hearth_activation(home)
            if activation.state not in {"active", "retired"}:
                raise RemoteHearthActivationError(
                    "source hearth has an unsupported activation state"
                )
            _ensure_local_handoff(home, handoff, descriptor)
            if activation.state == "active":
                write_hearth_activation_locked(
                    home,
                    HearthActivation(
                        actor_id=manifest.actor_id,
                        hearth_shard_id=manifest.hearth_shard_id,
                        runtime_generation=manifest.runtime_generation,
                        state="retired",
                    ),
                )
            receipt_path = home / HEARTH_RETIREMENT_RECEIPT_FILENAME
            if receipt_path.exists() or receipt_path.is_symlink():
                return load_hearth_handoff_receipt(
                    receipt_path,
                    handoff=handoff,
                    witness=source_witness,
                )
            receipt = create_hearth_handoff_receipt(
                handoff,
                phase="source_retired",
                witness=source_witness,
                witness_private_key=source_witness_private_key,
            )
            return _ensure_receipt(
                receipt_path,
                receipt,
                handoff=handoff,
                witness=source_witness,
            )
    except (
        HearthActivationError,
        HearthHandoffError,
        HearthManifestError,
        HearthReceiptError,
        OSError,
        ResidentIdentityError,
    ) as exc:
        raise RemoteHearthActivationError(str(exc)) from exc


def activate_destination_hearth(
    resident_dir: Path,
    retirement_receipt: HearthHandoffReceipt,
    *,
    destination_transport_public_key: X25519PublicKey,
    source_witness: HostWitnessDescriptor,
    destination_witness: HostWitnessDescriptor,
    destination_witness_private_key: Ed25519PrivateKey,
) -> HearthHandoffReceipt:
    """Verify source retirement, activate N+1, then witness that fact."""

    home = Path(resident_dir)
    try:
        descriptor = load_resident_identity_descriptor(home)
        handoff = load_hearth_handoff_authorization(
            home / HEARTH_HANDOFF_FILENAME,
            identity_descriptor=descriptor,
        )
        if (
            handoff.destination_host_key_id
            != transport_key_id(destination_transport_public_key)
            or handoff.destination_witness_id != destination_witness.witness_id
            or handoff.destination_witness_key_id != destination_witness.key_id
        ):
            raise RemoteHearthActivationError(
                "hearth handoff does not authorize this destination host"
            )
        _require_witness_private_key(
            destination_witness,
            destination_witness_private_key,
        )
        verified_retirement = HearthHandoffReceipt.from_dict(
            retirement_receipt.to_dict(),
            handoff=handoff,
            witness=source_witness,
        )
        if verified_retirement.phase != "source_retired":
            raise RemoteHearthActivationError(
                "destination activation requires a source-retirement receipt"
            )
        with HearthRuntimeLease(home):
            manifest = load_hearth_manifest(home)
            if (
                manifest.actor_id != handoff.actor_id
                or manifest.hearth_shard_id != handoff.hearth_shard_id
                or manifest.runtime_generation
                not in {handoff.source_generation, handoff.destination_generation}
            ):
                raise RemoteHearthActivationError(
                    "destination hearth is not an authorized successor generation"
                )
            _ensure_receipt(
                home / HEARTH_RETIREMENT_RECEIPT_FILENAME,
                verified_retirement,
                handoff=handoff,
                witness=source_witness,
            )
            if manifest.runtime_generation == handoff.source_generation:
                manifest = advance_hearth_manifest_generation(
                    home,
                    expected_generation=handoff.source_generation,
                )
            if activation_path(home).exists() or activation_path(home).is_symlink():
                activation = load_hearth_activation(home)
                if activation.state != "active":
                    raise RemoteHearthActivationError(
                        "destination hearth activation is not active"
                    )
            else:
                write_hearth_activation_locked(
                    home,
                    HearthActivation(
                        actor_id=manifest.actor_id,
                        hearth_shard_id=manifest.hearth_shard_id,
                        runtime_generation=manifest.runtime_generation,
                        state="active",
                    ),
                )
            receipt_path = home / HEARTH_ACTIVATION_RECEIPT_FILENAME
            if receipt_path.exists() or receipt_path.is_symlink():
                return load_hearth_handoff_receipt(
                    receipt_path,
                    handoff=handoff,
                    witness=destination_witness,
                )
            receipt = create_hearth_handoff_receipt(
                handoff,
                phase="destination_activated",
                witness=destination_witness,
                witness_private_key=destination_witness_private_key,
            )
            return _ensure_receipt(
                receipt_path,
                receipt,
                handoff=handoff,
                witness=destination_witness,
            )
    except (
        HearthActivationError,
        HearthHandoffError,
        HearthManifestError,
        HearthReceiptError,
        OSError,
        ResidentIdentityError,
    ) as exc:
        raise RemoteHearthActivationError(str(exc)) from exc
