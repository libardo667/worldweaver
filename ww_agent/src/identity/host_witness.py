# SPDX-License-Identifier: AGPL-3.0-or-later
"""Public shard identity used to witness hearth transfer state changes.

The node key remains outside the resident runtime. A resident may explicitly
bind its public key in one handoff, allowing narrow operator code to attest that
the source retired or the destination activated. This is witness evidence, not
ownership of the resident.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_BASE_FIELDS = {"schema", "schema_version", "node_id", "shard_type", "public_key"}
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_DESCRIPTOR_BYTES = 16 * 1024


class HostWitnessError(ValueError):
    """A public host witness descriptor is invalid or unsafe."""


def _decode(value: Any, *, label: str) -> bytes:
    encoded = str(value or "").strip()
    if (
        not isinstance(value, str)
        or value != encoded
        or not _BASE64URL_RE.fullmatch(encoded)
    ):
        raise HostWitnessError(f"Host witness {label} is invalid.")
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (TypeError, ValueError, binascii.Error) as exc:
        raise HostWitnessError(f"Host witness {label} is invalid.") from exc
    if len(decoded) != 32:
        raise HostWitnessError(f"Host witness {label} has the wrong size.")
    return decoded


def host_witness_key_id(public_key: str | Ed25519PublicKey) -> str:
    """Return the stable fingerprint used in resident-signed handoffs."""

    raw = (
        public_key.public_bytes_raw()
        if isinstance(public_key, Ed25519PublicKey)
        else _decode(public_key, label="public key")
    )
    return f"ed25519:{hashlib.sha256(raw).hexdigest()[:32]}"


@dataclass(frozen=True, slots=True)
class HostWitnessDescriptor:
    witness_id: str
    public_key: str
    key_id: str

    def __post_init__(self) -> None:
        if (
            len(self.witness_id) > 80
            or not _TOKEN_RE.fullmatch(self.witness_id)
            or self.key_id != host_witness_key_id(self.public_key)
        ):
            raise HostWitnessError("Host witness binding is invalid.")

    @property
    def public_key_object(self) -> Ed25519PublicKey:
        return Ed25519PublicKey.from_public_bytes(
            _decode(self.public_key, label="public key")
        )

    @classmethod
    def from_node_descriptor(cls, raw: Mapping[str, Any]) -> "HostWitnessDescriptor":
        if not isinstance(raw, Mapping):
            raise HostWitnessError("Host witness descriptor must be a JSON object.")
        expected_fields = set(_BASE_FIELDS)
        if raw.get("shard_type") != "world":
            expected_fields.add("city_id")
        if set(raw) != expected_fields:
            raise HostWitnessError("Host witness descriptor has unexpected fields.")
        if (
            raw.get("schema") != "worldweaver.node"
            or type(raw.get("schema_version")) is not int
            or raw.get("schema_version") != 1
        ):
            raise HostWitnessError("Host witness descriptor schema is unsupported.")
        witness_id = str(raw.get("node_id") or "").strip()
        if (
            raw.get("node_id") != witness_id
            or len(witness_id) > 80
            or not _TOKEN_RE.fullmatch(witness_id)
        ):
            raise HostWitnessError("Host witness node ID is invalid.")
        if raw.get("shard_type") not in {"city", "world", "neighborhood"}:
            raise HostWitnessError("Host witness shard type is invalid.")
        if "city_id" in raw:
            city_id = str(raw.get("city_id") or "").strip()
            if raw.get("city_id") != city_id or not _TOKEN_RE.fullmatch(city_id):
                raise HostWitnessError("Host witness city ID is invalid.")
        public_key = str(raw.get("public_key") or "").strip()
        if raw.get("public_key") != public_key:
            raise HostWitnessError("Host witness public key is invalid.")
        _decode(public_key, label="public key")
        return cls(
            witness_id=witness_id,
            public_key=public_key,
            key_id=host_witness_key_id(public_key),
        )


def load_host_witness_descriptor(path: str | Path) -> HostWitnessDescriptor:
    """Load a regular safe-to-share node descriptor as a host witness."""

    descriptor_path = Path(path).expanduser()
    if not descriptor_path.is_file() or descriptor_path.is_symlink():
        raise HostWitnessError(
            f"Host witness descriptor is missing or unsafe: {descriptor_path}"
        )
    try:
        encoded = descriptor_path.read_bytes()
        if len(encoded) > _MAX_DESCRIPTOR_BYTES:
            raise HostWitnessError("Host witness descriptor is too large.")
        raw = json.loads(encoded)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HostWitnessError(
            f"Could not load host witness descriptor: {descriptor_path}"
        ) from exc
    return HostWitnessDescriptor.from_node_descriptor(raw)
