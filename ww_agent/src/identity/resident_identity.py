# SPDX-License-Identifier: AGPL-3.0-or-later
"""Public, self-signed identity descriptor for one resident.

The descriptor is safe to review and share. It proves that its public key signed
the listed fields, but a city steward still decides whether to admit that
actor/key binding. This module never creates or stores a private key.
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

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.identity.hearth_manifest import HearthManifest, load_hearth_manifest

RESIDENT_IDENTITY_SCHEMA = "worldweaver.resident-identity"
RESIDENT_IDENTITY_VERSION = 1
RESIDENT_IDENTITY_FILENAME = "resident_identity.json"

_FIELDS = {
    "schema",
    "schema_version",
    "actor_id",
    "hearth_shard_id",
    "identity_public_key",
    "identity_key_id",
    "recovery_policy_version",
    "identity_signature",
}
_UNSIGNED_FIELDS = tuple(sorted(_FIELDS - {"identity_signature"}))
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_DESCRIPTOR_BYTES = 16 * 1024


class ResidentIdentityError(ValueError):
    """A resident public identity descriptor is invalid or inconsistent."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: Any, *, label: str, expected_size: int) -> bytes:
    encoded = str(value or "").strip()
    if not _BASE64URL_RE.fullmatch(encoded):
        raise ResidentIdentityError(f"Resident {label} is invalid.")
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (TypeError, ValueError, binascii.Error) as exc:
        raise ResidentIdentityError(f"Resident {label} is invalid.") from exc
    if len(decoded) != expected_size:
        raise ResidentIdentityError(f"Resident {label} has the wrong size.")
    return decoded


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def encoded_identity_public_key(key: Ed25519PublicKey) -> str:
    """Return the safe-to-share public key encoding used by city admission."""

    return _encode(key.public_bytes_raw())


def resident_identity_key_id(public_key: str | Ed25519PublicKey) -> str:
    """Return the city-compatible fingerprint for a resident identity key."""

    encoded = (
        encoded_identity_public_key(public_key)
        if isinstance(public_key, Ed25519PublicKey)
        else str(public_key or "").strip()
    )
    key_bytes = _decode(
        encoded,
        label="identity public key",
        expected_size=32,
    )
    return f"ed25519:{hashlib.sha256(key_bytes).hexdigest()[:32]}"


@dataclass(frozen=True, slots=True)
class ResidentIdentityDescriptor:
    actor_id: str
    hearth_shard_id: str
    identity_public_key: str
    identity_key_id: str
    recovery_policy_version: int
    identity_signature: str
    schema: str = RESIDENT_IDENTITY_SCHEMA
    schema_version: int = RESIDENT_IDENTITY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "actor_id": self.actor_id,
            "hearth_shard_id": self.hearth_shard_id,
            "identity_public_key": self.identity_public_key,
            "identity_key_id": self.identity_key_id,
            "recovery_policy_version": self.recovery_policy_version,
            "identity_signature": self.identity_signature,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ResidentIdentityDescriptor":
        if not isinstance(raw, Mapping) or set(raw) != _FIELDS:
            raise ResidentIdentityError(
                "Resident identity fields do not match version 1."
            )
        if (
            raw.get("schema") != RESIDENT_IDENTITY_SCHEMA
            or raw.get("schema_version") != RESIDENT_IDENTITY_VERSION
        ):
            raise ResidentIdentityError("Resident identity schema is unsupported.")
        actor_id = str(raw.get("actor_id") or "").strip()
        hearth_shard_id = str(raw.get("hearth_shard_id") or "").strip()
        if not _TOKEN_RE.fullmatch(actor_id) or len(actor_id) > 36:
            raise ResidentIdentityError("Resident actor ID is invalid.")
        if not _TOKEN_RE.fullmatch(hearth_shard_id) or len(hearth_shard_id) > 80:
            raise ResidentIdentityError("Resident hearth shard ID is invalid.")
        if hearth_shard_id != f"hearth:{actor_id}":
            raise ResidentIdentityError(
                "Resident hearth shard ID does not match the actor ID."
            )
        public_key = str(raw.get("identity_public_key") or "").strip()
        public_key_bytes = _decode(
            public_key,
            label="identity public key",
            expected_size=32,
        )
        key_id = str(raw.get("identity_key_id") or "").strip()
        if key_id != resident_identity_key_id(public_key):
            raise ResidentIdentityError("Resident identity key ID does not match.")
        policy_version = raw.get("recovery_policy_version")
        if (
            isinstance(policy_version, bool)
            or not isinstance(policy_version, int)
            or policy_version < 1
            or policy_version > (2**31) - 1
        ):
            raise ResidentIdentityError("Resident recovery policy version is invalid.")
        signature = str(raw.get("identity_signature") or "").strip()
        signature_bytes = _decode(
            signature,
            label="identity signature",
            expected_size=64,
        )
        unsigned = {key: raw[key] for key in _UNSIGNED_FIELDS}
        try:
            Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
                signature_bytes,
                _canonical_json(unsigned),
            )
        except (InvalidSignature, ValueError) as exc:
            raise ResidentIdentityError(
                "Resident identity signature is invalid."
            ) from exc
        return cls(
            actor_id=actor_id,
            hearth_shard_id=hearth_shard_id,
            identity_public_key=public_key,
            identity_key_id=key_id,
            recovery_policy_version=policy_version,
            identity_signature=signature,
        )


def create_resident_identity_descriptor(
    manifest: HearthManifest,
    *,
    identity_private_key: Ed25519PrivateKey,
    recovery_policy_version: int = 1,
) -> ResidentIdentityDescriptor:
    """Create one public descriptor from an injected private key."""

    public_key = encoded_identity_public_key(identity_private_key.public_key())
    unsigned: dict[str, Any] = {
        "schema": RESIDENT_IDENTITY_SCHEMA,
        "schema_version": RESIDENT_IDENTITY_VERSION,
        "actor_id": manifest.actor_id,
        "hearth_shard_id": manifest.hearth_shard_id,
        "identity_public_key": public_key,
        "identity_key_id": resident_identity_key_id(public_key),
        "recovery_policy_version": recovery_policy_version,
    }
    signature = _encode(identity_private_key.sign(_canonical_json(unsigned)))
    return ResidentIdentityDescriptor.from_dict(
        {**unsigned, "identity_signature": signature}
    )


def resident_identity_path(resident_dir: Path) -> Path:
    return Path(resident_dir) / "identity" / RESIDENT_IDENTITY_FILENAME


def load_resident_identity_descriptor(
    resident_dir: Path,
) -> ResidentIdentityDescriptor:
    """Load and verify a descriptor against the hearth's stable manifest."""

    path = resident_identity_path(resident_dir)
    if not path.is_file() or path.is_symlink():
        raise ResidentIdentityError(
            f"identity/{RESIDENT_IDENTITY_FILENAME} is missing or unsafe."
        )
    try:
        encoded = path.read_bytes()
        if len(encoded) > _MAX_DESCRIPTOR_BYTES:
            raise ResidentIdentityError("Resident identity descriptor is too large.")
        raw = json.loads(encoded)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ResidentIdentityError(
            "Resident identity descriptor is not valid UTF-8 JSON."
        ) from exc
    descriptor = ResidentIdentityDescriptor.from_dict(raw)
    manifest = load_hearth_manifest(resident_dir)
    if (
        descriptor.actor_id != manifest.actor_id
        or descriptor.hearth_shard_id != manifest.hearth_shard_id
    ):
        raise ResidentIdentityError(
            "Resident identity descriptor does not match the hearth manifest."
        )
    return descriptor


def write_resident_identity_descriptor(
    resident_dir: Path,
    descriptor: ResidentIdentityDescriptor,
) -> None:
    """Verify and atomically write one public descriptor without replacement."""

    home = Path(resident_dir)
    verified = ResidentIdentityDescriptor.from_dict(descriptor.to_dict())
    manifest = load_hearth_manifest(home)
    if (
        verified.actor_id != manifest.actor_id
        or verified.hearth_shard_id != manifest.hearth_shard_id
    ):
        raise ResidentIdentityError(
            "Resident identity descriptor does not match the hearth manifest."
        )
    path = resident_identity_path(home)
    if path.exists() or path.is_symlink():
        raise ResidentIdentityError(
            f"refusing to replace identity/{RESIDENT_IDENTITY_FILENAME}"
        )
    encoded = (json.dumps(verified.to_dict(), indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except OSError as exc:
        raise ResidentIdentityError(
            f"Could not write resident identity descriptor: {exc}"
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
