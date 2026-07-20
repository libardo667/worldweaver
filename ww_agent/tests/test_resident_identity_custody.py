from __future__ import annotations

import base64

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import pytest

from src.identity.hearth_activation import HearthRuntimeLease
from src.identity.hearth_manifest import initialize_hearth_manifest
from src.identity.resident_identity import load_resident_identity_descriptor
from src.identity.resident_identity_custody import (
    ResidentIdentityCustodyError,
    initialize_resident_identity_custody,
)
from src.identity.resident_key_seal import (
    SEALED_RESIDENT_IDENTITY_FILENAME,
    load_resident_key_seal,
    open_sealed_resident_identity_private_key,
)


def _host_key(tmp_path):
    private_key = X25519PrivateKey.generate()
    path = tmp_path / "transport.key"
    encoded = base64.urlsafe_b64encode(private_key.private_bytes_raw()).decode("ascii")
    path.write_text(encoded.rstrip("=") + "\n", encoding="utf-8")
    return path, private_key


def _home(tmp_path):
    home = tmp_path / "resident"
    identity = home / "identity"
    identity.mkdir(parents=True)
    (identity / "resident_id.txt").write_text("actor-test", encoding="utf-8")
    initialize_hearth_manifest(home)
    return home


def test_initialization_writes_public_card_and_only_a_host_sealed_private_key(tmp_path):
    home = _home(tmp_path)
    host_key_path, host_private_key = _host_key(tmp_path)

    descriptor = initialize_resident_identity_custody(
        home,
        host_transport_private_key_path=host_key_path,
    )

    assert load_resident_identity_descriptor(home) == descriptor
    seal_path = home / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME
    identity_private_key = open_sealed_resident_identity_private_key(
        load_resident_key_seal(seal_path),
        identity_descriptor=descriptor,
        recipient_transport_private_key=host_private_key,
    )
    assert identity_private_key.public_key().public_bytes_raw()
    assert not list(home.rglob("*.key"))
    assert seal_path.stat().st_mode & 0o077 == 0


def test_initialization_never_replaces_an_existing_identity(tmp_path):
    home = _home(tmp_path)
    host_key_path, _host_private_key = _host_key(tmp_path)
    initialize_resident_identity_custody(
        home,
        host_transport_private_key_path=host_key_path,
    )

    with pytest.raises(ResidentIdentityCustodyError, match="already exists"):
        initialize_resident_identity_custody(
            home,
            host_transport_private_key_path=host_key_path,
        )


def test_initialization_refuses_a_running_hearth(tmp_path):
    home = _home(tmp_path)
    host_key_path, _host_private_key = _host_key(tmp_path)
    lease = HearthRuntimeLease(home).acquire()
    try:
        with pytest.raises(RuntimeError, match="already running"):
            initialize_resident_identity_custody(
                home,
                host_transport_private_key_path=host_key_path,
            )
    finally:
        lease.release()
