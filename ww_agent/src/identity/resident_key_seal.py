# SPDX-License-Identifier: AGPL-3.0-or-later
"""Encrypt one resident identity key for the currently authorized hearth host.

The sealed file is host-local custody material, not portable identity. A later
transfer must open it in memory and re-encrypt the key for the reviewed next
host; ordinary plaintext hearth packages must continue to exclude it.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.identity.hearth_envelope import (
    encoded_transport_public_key,
    transport_key_id,
)
from src.identity.resident_identity import (
    ResidentIdentityDescriptor,
    encoded_identity_public_key,
)

SEALED_RESIDENT_IDENTITY_FILENAME = "resident_identity.sealed.json"
SEALED_RESIDENT_IDENTITY_SCHEMA = "worldweaver.sealed-resident-identity"
SEALED_RESIDENT_IDENTITY_VERSION = 1
SEALED_RESIDENT_IDENTITY_CIPHER = "X25519-HKDF-SHA256+A256GCM"

_MAX_SEALED_BYTES = 64 * 1024
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_FIELDS = {
    "schema",
    "schema_version",
    "cipher",
    "actor_id",
    "hearth_shard_id",
    "identity_key_id",
    "recipient_key_id",
    "ephemeral_public_key",
    "nonce",
    "ciphertext",
}
_HEADER_FIELDS = tuple(sorted(_FIELDS - {"ciphertext"}))
_HKDF_INFO = b"worldweaver.sealed-resident-identity.v1"


class ResidentKeySealError(ValueError):
    """A host-sealed resident identity key is malformed or cannot be opened."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: Any, *, label: str, expected_size: int | None = None) -> bytes:
    encoded = str(value or "").strip()
    if (
        not isinstance(value, str)
        or value != encoded
        or not _BASE64URL_RE.fullmatch(encoded)
    ):
        raise ResidentKeySealError(f"Sealed resident identity {label} is invalid.")
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (TypeError, ValueError, binascii.Error) as exc:
        raise ResidentKeySealError(
            f"Sealed resident identity {label} is invalid."
        ) from exc
    if expected_size is not None and len(decoded) != expected_size:
        raise ResidentKeySealError(
            f"Sealed resident identity {label} has the wrong size."
        )
    return decoded


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _content_key(
    private_key: X25519PrivateKey,
    public_key: X25519PublicKey,
) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_HKDF_INFO,
    ).derive(private_key.exchange(public_key))


def _parse(encoded_seal: bytes) -> dict[str, Any]:
    if len(encoded_seal) > _MAX_SEALED_BYTES:
        raise ResidentKeySealError("Sealed resident identity file is too large.")
    try:
        raw = json.loads(bytes(encoded_seal))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ResidentKeySealError(
            "Sealed resident identity is not valid UTF-8 JSON."
        ) from exc
    if not isinstance(raw, dict) or set(raw) != _FIELDS:
        raise ResidentKeySealError(
            "Sealed resident identity fields do not match version 1."
        )
    if (
        raw.get("schema") != SEALED_RESIDENT_IDENTITY_SCHEMA
        or type(raw.get("schema_version")) is not int
        or raw.get("schema_version") != SEALED_RESIDENT_IDENTITY_VERSION
        or raw.get("cipher") != SEALED_RESIDENT_IDENTITY_CIPHER
    ):
        raise ResidentKeySealError("Sealed resident identity schema is unsupported.")
    actor_id = str(raw.get("actor_id") or "").strip()
    hearth_shard_id = str(raw.get("hearth_shard_id") or "").strip()
    if raw.get("actor_id") != actor_id or raw.get("hearth_shard_id") != hearth_shard_id:
        raise ResidentKeySealError("Sealed resident identity binding is invalid.")
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", actor_id) or not re.fullmatch(
        r"[A-Za-z0-9._:-]{1,128}", hearth_shard_id
    ):
        raise ResidentKeySealError("Sealed resident identity binding is invalid.")
    if not re.fullmatch(r"ed25519:[0-9a-f]{32}", str(raw.get("identity_key_id") or "")):
        raise ResidentKeySealError("Sealed resident identity key ID is invalid.")
    if not re.fullmatch(r"x25519:[0-9a-f]{32}", str(raw.get("recipient_key_id") or "")):
        raise ResidentKeySealError("Sealed resident recipient key ID is invalid.")
    _decode(raw.get("ephemeral_public_key"), label="ephemeral key", expected_size=32)
    _decode(raw.get("nonce"), label="nonce", expected_size=12)
    ciphertext = _decode(raw.get("ciphertext"), label="ciphertext")
    if len(ciphertext) != 48:
        raise ResidentKeySealError(
            "Sealed resident identity ciphertext has the wrong size."
        )
    return raw


def seal_resident_identity_private_key(
    identity_private_key: Ed25519PrivateKey,
    *,
    identity_descriptor: ResidentIdentityDescriptor,
    recipient_transport_public_key: X25519PublicKey,
) -> bytes:
    """Encrypt one identity key for the current host and bind it to its card."""

    descriptor = ResidentIdentityDescriptor.from_dict(identity_descriptor.to_dict())
    if (
        encoded_identity_public_key(identity_private_key.public_key())
        != descriptor.identity_public_key
    ):
        raise ResidentKeySealError(
            "Resident identity private key does not match the public identity card."
        )
    ephemeral_private = X25519PrivateKey.generate()
    nonce = os.urandom(12)
    header: dict[str, Any] = {
        "schema": SEALED_RESIDENT_IDENTITY_SCHEMA,
        "schema_version": SEALED_RESIDENT_IDENTITY_VERSION,
        "cipher": SEALED_RESIDENT_IDENTITY_CIPHER,
        "actor_id": descriptor.actor_id,
        "hearth_shard_id": descriptor.hearth_shard_id,
        "identity_key_id": descriptor.identity_key_id,
        "recipient_key_id": transport_key_id(recipient_transport_public_key),
        "ephemeral_public_key": encoded_transport_public_key(
            ephemeral_private.public_key()
        ),
        "nonce": _encode(nonce),
    }
    ciphertext = AESGCM(
        _content_key(ephemeral_private, recipient_transport_public_key)
    ).encrypt(
        nonce,
        identity_private_key.private_bytes_raw(),
        _canonical_json(header),
    )
    return (
        json.dumps(
            {**header, "ciphertext": _encode(ciphertext)},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def open_sealed_resident_identity_private_key(
    encoded_seal: bytes,
    *,
    identity_descriptor: ResidentIdentityDescriptor,
    recipient_transport_private_key: X25519PrivateKey,
) -> Ed25519PrivateKey:
    """Authenticate and open one key seal for the expected card and host."""

    descriptor = ResidentIdentityDescriptor.from_dict(identity_descriptor.to_dict())
    raw = _parse(encoded_seal)
    if (
        raw["actor_id"] != descriptor.actor_id
        or raw["hearth_shard_id"] != descriptor.hearth_shard_id
        or raw["identity_key_id"] != descriptor.identity_key_id
    ):
        raise ResidentKeySealError(
            "Sealed resident identity does not match the public identity card."
        )
    if raw["recipient_key_id"] != transport_key_id(
        recipient_transport_private_key.public_key()
    ):
        raise ResidentKeySealError(
            "Sealed resident identity belongs to another hearth host."
        )
    ephemeral_public = X25519PublicKey.from_public_bytes(
        _decode(
            raw["ephemeral_public_key"],
            label="ephemeral key",
            expected_size=32,
        )
    )
    header = {field: raw[field] for field in _HEADER_FIELDS}
    try:
        private_bytes = AESGCM(
            _content_key(recipient_transport_private_key, ephemeral_public)
        ).decrypt(
            _decode(raw["nonce"], label="nonce", expected_size=12),
            _decode(raw["ciphertext"], label="ciphertext"),
            _canonical_json(header),
        )
    except (InvalidTag, ValueError) as exc:
        raise ResidentKeySealError(
            "Sealed resident identity could not be authenticated."
        ) from exc
    try:
        private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
    except ValueError as exc:
        raise ResidentKeySealError(
            "Sealed resident identity private key is invalid."
        ) from exc
    if (
        encoded_identity_public_key(private_key.public_key())
        != descriptor.identity_public_key
    ):
        raise ResidentKeySealError(
            "Sealed private key does not match the public identity card."
        )
    return private_key


def load_resident_key_seal(path: str | Path) -> bytes:
    """Read and structurally validate one regular host-local sealed key file."""

    seal_path = Path(path).expanduser()
    if not seal_path.is_file() or seal_path.is_symlink():
        raise ResidentKeySealError(
            f"Sealed resident identity is missing or unsafe: {seal_path}"
        )
    try:
        encoded = seal_path.read_bytes()
    except OSError as exc:
        raise ResidentKeySealError(
            f"Could not read sealed resident identity: {seal_path}"
        ) from exc
    _parse(encoded)
    return encoded


def write_resident_key_seal(path: str | Path, encoded_seal: bytes) -> None:
    """Atomically create one owner-only sealed key file without replacement."""

    seal_path = Path(path)
    _parse(encoded_seal)
    if seal_path.exists() or seal_path.is_symlink():
        raise ResidentKeySealError(
            f"Refusing to replace existing sealed resident identity: {seal_path}"
        )
    if not seal_path.parent.is_dir() or seal_path.parent.is_symlink():
        raise ResidentKeySealError(
            f"Sealed resident identity parent is missing or unsafe: {seal_path.parent}"
        )
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=seal_path.parent,
            prefix=f".{seal_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(encoded_seal)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, seal_path)
        seal_path.chmod(0o600)
    except OSError as exc:
        raise ResidentKeySealError(
            f"Could not write sealed resident identity: {seal_path}"
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
