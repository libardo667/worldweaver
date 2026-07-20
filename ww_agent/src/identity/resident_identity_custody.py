# SPDX-License-Identifier: AGPL-3.0-or-later
"""Create a new resident identity directly into one host's sealed custody."""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.identity.hearth_activation import HearthRuntimeLease
from src.identity.hearth_envelope import load_transport_private_key
from src.identity.hearth_manifest import load_hearth_manifest
from src.identity.hearth_permissions import secure_hearth_permissions
from src.identity.resident_identity import (
    ResidentIdentityDescriptor,
    create_resident_identity_descriptor,
    resident_identity_path,
    write_resident_identity_descriptor,
)
from src.identity.resident_key_seal import (
    SEALED_RESIDENT_IDENTITY_FILENAME,
    seal_resident_identity_private_key,
    write_resident_key_seal,
)


class ResidentIdentityCustodyError(ValueError):
    """A stopped hearth cannot safely receive its first identity key."""


def initialize_resident_identity_custody(
    resident_dir: Path,
    *,
    host_transport_private_key_path: str | Path,
) -> ResidentIdentityDescriptor:
    """Create one identity card and host seal without a plaintext key file."""

    home = Path(resident_dir)
    descriptor_path = resident_identity_path(home)
    seal_path = home / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME
    if descriptor_path.exists() or descriptor_path.is_symlink():
        raise ResidentIdentityCustodyError(
            "Resident identity card already exists; initialization never replaces it."
        )
    if seal_path.exists() or seal_path.is_symlink():
        raise ResidentIdentityCustodyError(
            "Resident identity seal already exists; initialization never replaces it."
        )

    lease = HearthRuntimeLease(home).acquire()
    descriptor_written = False
    try:
        manifest = load_hearth_manifest(home)
        host_private_key = load_transport_private_key(host_transport_private_key_path)
        identity_private_key = Ed25519PrivateKey.generate()
        descriptor = create_resident_identity_descriptor(
            manifest,
            identity_private_key=identity_private_key,
        )
        encoded_seal = seal_resident_identity_private_key(
            identity_private_key,
            identity_descriptor=descriptor,
            recipient_transport_public_key=host_private_key.public_key(),
        )
        try:
            write_resident_identity_descriptor(home, descriptor)
            descriptor_written = True
            write_resident_key_seal(seal_path, encoded_seal)
        except BaseException:
            if descriptor_written and not seal_path.exists():
                descriptor_path.unlink(missing_ok=True)
            raise
        secure_hearth_permissions(home)
        return descriptor
    finally:
        lease.release()
