# SPDX-License-Identifier: AGPL-3.0-or-later
"""A host-only X25519 identity for receiving encrypted hearth packages.

This key is separate from node federation signing and resident identity. It can
decrypt packages addressed to this temporary host, and nothing else.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)

HEARTH_TRANSPORT_SCHEMA = "worldweaver.hearth-transport"
HEARTH_TRANSPORT_VERSION = 1
_FIELDS = {
    "schema",
    "schema_version",
    "transport_key_id",
    "transport_public_key",
}
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class HearthTransportError(ValueError):
    """A host hearth-transport identity is malformed or unsafe."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: Any, *, label: str) -> bytes:
    encoded = str(value or "").strip()
    if not isinstance(value, str) or value != encoded or not _BASE64URL_RE.fullmatch(encoded):
        raise HearthTransportError(f"Hearth transport {label} is invalid.")
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (TypeError, ValueError, binascii.Error) as exc:
        raise HearthTransportError(f"Hearth transport {label} is invalid.") from exc
    if len(decoded) != 32:
        raise HearthTransportError(f"Hearth transport {label} has the wrong size.")
    return decoded


def encoded_transport_public_key(key: X25519PublicKey) -> str:
    return _encode(key.public_bytes_raw())


def hearth_transport_key_id(public_key: str | X25519PublicKey) -> str:
    encoded = encoded_transport_public_key(public_key) if isinstance(public_key, X25519PublicKey) else public_key
    raw = _decode(encoded, label="public key")
    return f"x25519:{hashlib.sha256(raw).hexdigest()[:32]}"


@dataclass(frozen=True, slots=True)
class HearthTransportDescriptor:
    transport_key_id: str
    transport_public_key: str
    schema: str = HEARTH_TRANSPORT_SCHEMA
    schema_version: int = HEARTH_TRANSPORT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "transport_key_id": self.transport_key_id,
            "transport_public_key": self.transport_public_key,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "HearthTransportDescriptor":
        if not isinstance(raw, Mapping) or set(raw) != _FIELDS:
            raise HearthTransportError("Hearth transport descriptor fields do not match version 1.")
        if raw.get("schema") != HEARTH_TRANSPORT_SCHEMA or type(raw.get("schema_version")) is not int or raw.get("schema_version") != HEARTH_TRANSPORT_VERSION:
            raise HearthTransportError("Hearth transport descriptor schema is unsupported.")
        public_key = str(raw.get("transport_public_key") or "").strip()
        if not isinstance(raw.get("transport_public_key"), str) or raw.get("transport_public_key") != public_key:
            raise HearthTransportError("Hearth transport public key is invalid.")
        _decode(public_key, label="public key")
        key_id = str(raw.get("transport_key_id") or "").strip()
        if not isinstance(raw.get("transport_key_id"), str) or raw.get("transport_key_id") != key_id or key_id != hearth_transport_key_id(public_key):
            raise HearthTransportError("Hearth transport key ID does not match.")
        return cls(
            transport_key_id=key_id,
            transport_public_key=public_key,
        )


def _write_new(path: Path, content: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except OSError as exc:
        raise HearthTransportError(f"Could not write {path}: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def generate_hearth_transport_identity(
    *,
    private_key_path: Path,
    descriptor_path: Path,
) -> HearthTransportDescriptor:
    """Create one host transport key and its safe-to-share public descriptor."""

    private_path = Path(private_key_path)
    public_path = Path(descriptor_path)
    for path in (private_path, public_path):
        if path.exists() or path.is_symlink():
            raise HearthTransportError(f"Refusing to replace existing path: {path}")
    private_key = X25519PrivateKey.generate()
    public_key = encoded_transport_public_key(private_key.public_key())
    descriptor = HearthTransportDescriptor(
        transport_key_id=hearth_transport_key_id(public_key),
        transport_public_key=public_key,
    )
    private_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.parent.chmod(0o700)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    wrote_private = False
    try:
        _write_new(private_path, f"{_encode(private_key.private_bytes_raw())}\n".encode())
        wrote_private = True
        private_path.chmod(0o600)
        _write_new(
            public_path,
            (json.dumps(descriptor.to_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
    except Exception:
        if wrote_private:
            private_path.unlink(missing_ok=True)
        raise
    return descriptor


def load_hearth_transport_private_key(path: str | Path) -> X25519PrivateKey:
    key_path = Path(path).expanduser()
    if not key_path.is_file() or key_path.is_symlink():
        raise HearthTransportError(f"Hearth transport private key is missing or unsafe: {key_path}")
    try:
        raw = _decode(key_path.read_text(encoding="utf-8").strip(), label="private key")
        return X25519PrivateKey.from_private_bytes(raw)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise HearthTransportError(f"Could not load hearth transport private key: {key_path}") from exc
