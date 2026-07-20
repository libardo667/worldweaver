# SPDX-License-Identifier: AGPL-3.0-or-later
"""Resident-signed authorization for one orderly hearth host handoff.

This record coordinates cooperating hosts. It does not prove that a host erased
an undisclosed copy and does not turn either host into the resident's owner.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

from src.identity.hearth_envelope import transport_key_id
from src.identity.hearth_manifest import HearthManifest
from src.identity.resident_identity import (
    ResidentIdentityDescriptor,
    encoded_identity_public_key,
)

HEARTH_HANDOFF_SCHEMA = "worldweaver.hearth-handoff"
HEARTH_HANDOFF_VERSION = 1
HEARTH_HANDOFF_FILENAME = "hearth_handoff.json"
_MAX_HANDOFF_BYTES = 64 * 1024
_FIELDS = {
    "schema",
    "schema_version",
    "transfer_id",
    "actor_id",
    "hearth_shard_id",
    "identity_key_id",
    "source_generation",
    "destination_generation",
    "source_host_key_id",
    "destination_host_key_id",
    "resident_signature",
}
_UNSIGNED_FIELDS = tuple(sorted(_FIELDS - {"resident_signature"}))
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_KEY_ID_RE = re.compile(r"^x25519:[0-9a-f]{32}$")
_TRANSFER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{32}$")
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class HearthHandoffError(ValueError):
    """A resident host-handoff authorization is invalid."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: Any, *, label: str, expected_size: int) -> bytes:
    encoded = str(value or "").strip()
    if (
        not isinstance(value, str)
        or value != encoded
        or not _BASE64URL_RE.fullmatch(encoded)
    ):
        raise HearthHandoffError(f"Hearth handoff {label} is invalid.")
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (TypeError, ValueError, binascii.Error) as exc:
        raise HearthHandoffError(f"Hearth handoff {label} is invalid.") from exc
    if len(decoded) != expected_size:
        raise HearthHandoffError(f"Hearth handoff {label} has the wrong size.")
    return decoded


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class HearthHandoffAuthorization:
    transfer_id: str
    actor_id: str
    hearth_shard_id: str
    identity_key_id: str
    source_generation: int
    destination_generation: int
    source_host_key_id: str
    destination_host_key_id: str
    resident_signature: str
    schema: str = HEARTH_HANDOFF_SCHEMA
    schema_version: int = HEARTH_HANDOFF_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "transfer_id": self.transfer_id,
            "actor_id": self.actor_id,
            "hearth_shard_id": self.hearth_shard_id,
            "identity_key_id": self.identity_key_id,
            "source_generation": self.source_generation,
            "destination_generation": self.destination_generation,
            "source_host_key_id": self.source_host_key_id,
            "destination_host_key_id": self.destination_host_key_id,
            "resident_signature": self.resident_signature,
        }

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
        *,
        identity_descriptor: ResidentIdentityDescriptor,
    ) -> "HearthHandoffAuthorization":
        descriptor = ResidentIdentityDescriptor.from_dict(identity_descriptor.to_dict())
        if not isinstance(raw, Mapping) or set(raw) != _FIELDS:
            raise HearthHandoffError("Hearth handoff fields do not match version 1.")
        if (
            raw.get("schema") != HEARTH_HANDOFF_SCHEMA
            or type(raw.get("schema_version")) is not int
            or raw.get("schema_version") != HEARTH_HANDOFF_VERSION
        ):
            raise HearthHandoffError("Hearth handoff schema is unsupported.")
        transfer_id = str(raw.get("transfer_id") or "").strip()
        actor_id = str(raw.get("actor_id") or "").strip()
        hearth_shard_id = str(raw.get("hearth_shard_id") or "").strip()
        identity_key_id = str(raw.get("identity_key_id") or "").strip()
        source_host = str(raw.get("source_host_key_id") or "").strip()
        destination_host = str(raw.get("destination_host_key_id") or "").strip()
        if raw.get("transfer_id") != transfer_id or not _TRANSFER_ID_RE.fullmatch(
            transfer_id
        ):
            raise HearthHandoffError("Hearth handoff transfer ID is invalid.")
        if (
            raw.get("actor_id") != actor_id
            or raw.get("hearth_shard_id") != hearth_shard_id
            or not _TOKEN_RE.fullmatch(actor_id)
            or not _TOKEN_RE.fullmatch(hearth_shard_id)
        ):
            raise HearthHandoffError("Hearth handoff resident binding is invalid.")
        if (
            actor_id != descriptor.actor_id
            or hearth_shard_id != descriptor.hearth_shard_id
            or identity_key_id != descriptor.identity_key_id
        ):
            raise HearthHandoffError(
                "Hearth handoff does not match the resident identity card."
            )
        source_generation = raw.get("source_generation")
        destination_generation = raw.get("destination_generation")
        if (
            isinstance(source_generation, bool)
            or not isinstance(source_generation, int)
            or source_generation < 1
            or isinstance(destination_generation, bool)
            or not isinstance(destination_generation, int)
            or destination_generation != source_generation + 1
        ):
            raise HearthHandoffError(
                "Hearth handoff must advance exactly one runtime generation."
            )
        if (
            raw.get("source_host_key_id") != source_host
            or raw.get("destination_host_key_id") != destination_host
            or not _KEY_ID_RE.fullmatch(source_host)
            or not _KEY_ID_RE.fullmatch(destination_host)
            or source_host == destination_host
        ):
            raise HearthHandoffError("Hearth handoff host binding is invalid.")
        signature = str(raw.get("resident_signature") or "").strip()
        signature_bytes = _decode(signature, label="signature", expected_size=64)
        unsigned = {field: raw[field] for field in _UNSIGNED_FIELDS}
        try:
            Ed25519PublicKey.from_public_bytes(
                _decode(
                    descriptor.identity_public_key,
                    label="resident public key",
                    expected_size=32,
                )
            ).verify(signature_bytes, _canonical_json(unsigned))
        except (InvalidSignature, ValueError) as exc:
            raise HearthHandoffError(
                "Hearth handoff resident signature is invalid."
            ) from exc
        return cls(
            transfer_id=transfer_id,
            actor_id=actor_id,
            hearth_shard_id=hearth_shard_id,
            identity_key_id=identity_key_id,
            source_generation=source_generation,
            destination_generation=destination_generation,
            source_host_key_id=source_host,
            destination_host_key_id=destination_host,
            resident_signature=signature,
        )


def create_hearth_handoff_authorization(
    manifest: HearthManifest,
    *,
    identity_descriptor: ResidentIdentityDescriptor,
    identity_private_key: Ed25519PrivateKey,
    source_transport_public_key: X25519PublicKey,
    destination_transport_public_key: X25519PublicKey,
) -> HearthHandoffAuthorization:
    """Sign one exact N-to-N+1 transition between reviewed host keys."""

    descriptor = ResidentIdentityDescriptor.from_dict(identity_descriptor.to_dict())
    if (
        manifest.actor_id != descriptor.actor_id
        or manifest.hearth_shard_id != descriptor.hearth_shard_id
    ):
        raise HearthHandoffError(
            "Resident identity card does not match the hearth manifest."
        )
    if (
        encoded_identity_public_key(identity_private_key.public_key())
        != descriptor.identity_public_key
    ):
        raise HearthHandoffError(
            "Resident identity key does not match the public identity card."
        )
    unsigned: dict[str, Any] = {
        "schema": HEARTH_HANDOFF_SCHEMA,
        "schema_version": HEARTH_HANDOFF_VERSION,
        "transfer_id": secrets.token_urlsafe(24),
        "actor_id": manifest.actor_id,
        "hearth_shard_id": manifest.hearth_shard_id,
        "identity_key_id": descriptor.identity_key_id,
        "source_generation": manifest.runtime_generation,
        "destination_generation": manifest.runtime_generation + 1,
        "source_host_key_id": transport_key_id(source_transport_public_key),
        "destination_host_key_id": transport_key_id(destination_transport_public_key),
    }
    return HearthHandoffAuthorization.from_dict(
        {
            **unsigned,
            "resident_signature": _encode(
                identity_private_key.sign(_canonical_json(unsigned))
            ),
        },
        identity_descriptor=descriptor,
    )


def encode_hearth_handoff_authorization(
    authorization: HearthHandoffAuthorization,
    *,
    identity_descriptor: ResidentIdentityDescriptor,
) -> bytes:
    """Verify and encode one handoff for transfer or host-local storage."""

    verified = HearthHandoffAuthorization.from_dict(
        authorization.to_dict(),
        identity_descriptor=identity_descriptor,
    )
    return (json.dumps(verified.to_dict(), indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def decode_hearth_handoff_authorization(
    encoded: bytes,
    *,
    identity_descriptor: ResidentIdentityDescriptor,
) -> HearthHandoffAuthorization:
    """Decode and verify one bounded UTF-8 handoff document."""

    if len(encoded) > _MAX_HANDOFF_BYTES:
        raise HearthHandoffError("Hearth handoff document is too large.")
    try:
        raw = json.loads(bytes(encoded))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HearthHandoffError(
            "Hearth handoff document is not valid UTF-8 JSON."
        ) from exc
    return HearthHandoffAuthorization.from_dict(
        raw,
        identity_descriptor=identity_descriptor,
    )


def load_hearth_handoff_authorization(
    path: str | Path,
    *,
    identity_descriptor: ResidentIdentityDescriptor,
) -> HearthHandoffAuthorization:
    """Load one regular handoff file and verify its resident signature."""

    handoff_path = Path(path).expanduser()
    if not handoff_path.is_file() or handoff_path.is_symlink():
        raise HearthHandoffError(f"Hearth handoff is missing or unsafe: {handoff_path}")
    try:
        encoded = handoff_path.read_bytes()
    except OSError as exc:
        raise HearthHandoffError(
            f"Could not read hearth handoff: {handoff_path}"
        ) from exc
    return decode_hearth_handoff_authorization(
        encoded,
        identity_descriptor=identity_descriptor,
    )


def write_hearth_handoff_authorization(
    path: str | Path,
    authorization: HearthHandoffAuthorization,
    *,
    identity_descriptor: ResidentIdentityDescriptor,
) -> None:
    """Create one owner-only handoff file without replacing another record."""

    handoff_path = Path(path)
    encoded = encode_hearth_handoff_authorization(
        authorization,
        identity_descriptor=identity_descriptor,
    )
    if handoff_path.exists() or handoff_path.is_symlink():
        raise HearthHandoffError(
            f"Refusing to replace existing hearth handoff: {handoff_path}"
        )
    if not handoff_path.parent.is_dir() or handoff_path.parent.is_symlink():
        raise HearthHandoffError(
            f"Hearth handoff parent is missing or unsafe: {handoff_path.parent}"
        )
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=handoff_path.parent,
            prefix=f".{handoff_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, handoff_path)
        handoff_path.chmod(0o600)
    except OSError as exc:
        raise HearthHandoffError(f"Could not write hearth handoff: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
