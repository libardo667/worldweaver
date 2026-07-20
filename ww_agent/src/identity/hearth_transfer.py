# SPDX-License-Identifier: AGPL-3.0-or-later
"""In-memory payload for moving a resident key with an encrypted hearth.

This payload must only exist inside an authenticated ``hearth_envelope``. It
keeps the ordinary portable archive secret-free while allowing a reviewed next
host to reseal the resident identity key without writing that key as a file.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import stat
from typing import Any
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.identity.hearth_handoff import (
    HearthHandoffAuthorization,
    decode_hearth_handoff_authorization,
    encode_hearth_handoff_authorization,
)
from src.identity.hearth_manifest import HearthManifest
from src.identity.resident_identity import (
    ResidentIdentityDescriptor,
    encoded_identity_public_key,
)

HEARTH_TRANSFER_SCHEMA = "worldweaver.hearth-transfer-payload"
HEARTH_TRANSFER_VERSION = 2
HEARTH_TRANSFER_METADATA = "HEARTH_TRANSFER.json"
HEARTH_TRANSFER_ARCHIVE = "hearth.wwhearth"
HEARTH_TRANSFER_IDENTITY_KEY = "resident-identity.key"
HEARTH_TRANSFER_HANDOFF = "HEARTH_HANDOFF.json"

_TRANSFER_FIELDS = {
    "schema",
    "schema_version",
    "actor_id",
    "hearth_shard_id",
    "runtime_generation",
    "identity_key_id",
    "archive_size",
    "archive_sha256",
}
_TRANSFER_MEMBERS = {
    HEARTH_TRANSFER_METADATA,
    HEARTH_TRANSFER_ARCHIVE,
    HEARTH_TRANSFER_IDENTITY_KEY,
    HEARTH_TRANSFER_HANDOFF,
}
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_MAX_METADATA_BYTES = 64 * 1024
_MAX_ARCHIVE_BYTES = 64 * 1024 * 1024 * 1024


class HearthTransferError(ValueError):
    """An inner host-to-host transfer payload is invalid."""


@dataclass(frozen=True, slots=True)
class OpenedHearthTransfer:
    archive: bytes
    identity_private_key: Ed25519PrivateKey
    actor_id: str
    hearth_shard_id: str
    runtime_generation: int
    handoff_authorization: HearthHandoffAuthorization


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _zip_file_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=_FIXED_ZIP_TIME)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    return info


def build_hearth_transfer_payload(
    archive: bytes,
    *,
    manifest: HearthManifest,
    identity_descriptor: ResidentIdentityDescriptor,
    identity_private_key: Ed25519PrivateKey,
    handoff_authorization: HearthHandoffAuthorization,
) -> bytes:
    """Build the secret-bearing inner payload entirely in memory."""

    hearth_archive = bytes(archive)
    descriptor = ResidentIdentityDescriptor.from_dict(identity_descriptor.to_dict())
    if len(hearth_archive) > _MAX_ARCHIVE_BYTES:
        raise HearthTransferError("Portable hearth archive exceeds the transfer limit.")
    if (
        descriptor.actor_id != manifest.actor_id
        or descriptor.hearth_shard_id != manifest.hearth_shard_id
    ):
        raise HearthTransferError(
            "Resident identity card does not match the hearth manifest."
        )
    if (
        encoded_identity_public_key(identity_private_key.public_key())
        != descriptor.identity_public_key
    ):
        raise HearthTransferError(
            "Resident identity key does not match the public identity card."
        )
    handoff = HearthHandoffAuthorization.from_dict(
        handoff_authorization.to_dict(),
        identity_descriptor=descriptor,
    )
    if (
        handoff.actor_id != manifest.actor_id
        or handoff.hearth_shard_id != manifest.hearth_shard_id
        or handoff.source_generation != manifest.runtime_generation
    ):
        raise HearthTransferError(
            "Hearth handoff does not match the portable hearth generation."
        )

    metadata = {
        "schema": HEARTH_TRANSFER_SCHEMA,
        "schema_version": HEARTH_TRANSFER_VERSION,
        "actor_id": manifest.actor_id,
        "hearth_shard_id": manifest.hearth_shard_id,
        "runtime_generation": manifest.runtime_generation,
        "identity_key_id": descriptor.identity_key_id,
        "archive_size": len(hearth_archive),
        "archive_sha256": hashlib.sha256(hearth_archive).hexdigest(),
    }
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as transfer:
        transfer.writestr(
            _zip_file_info(HEARTH_TRANSFER_METADATA), _canonical_json(metadata)
        )
        transfer.writestr(_zip_file_info(HEARTH_TRANSFER_ARCHIVE), hearth_archive)
        transfer.writestr(
            _zip_file_info(HEARTH_TRANSFER_IDENTITY_KEY),
            identity_private_key.private_bytes_raw(),
        )
        transfer.writestr(
            _zip_file_info(HEARTH_TRANSFER_HANDOFF),
            encode_hearth_handoff_authorization(
                handoff,
                identity_descriptor=descriptor,
            ),
        )
    return payload.getvalue()


def _read_metadata(transfer: zipfile.ZipFile) -> dict[str, Any]:
    names = transfer.namelist()
    if len(names) != len(set(names)) or set(names) != _TRANSFER_MEMBERS:
        raise HearthTransferError(
            "Transfer members do not match the version 2 payload."
        )
    for info in transfer.infolist():
        mode = info.external_attr >> 16
        if (
            info.is_dir()
            or stat.S_ISLNK(mode)
            or info.flag_bits & 0x1
            or info.compress_type != zipfile.ZIP_STORED
        ):
            raise HearthTransferError(
                f"Transfer member is not a plain regular file: {info.filename}"
            )
    metadata_info = transfer.getinfo(HEARTH_TRANSFER_METADATA)
    if metadata_info.file_size > _MAX_METADATA_BYTES:
        raise HearthTransferError("Transfer metadata is too large.")
    try:
        raw = json.loads(transfer.read(HEARTH_TRANSFER_METADATA))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HearthTransferError("Transfer metadata is not valid UTF-8 JSON.") from exc
    if not isinstance(raw, dict) or set(raw) != _TRANSFER_FIELDS:
        raise HearthTransferError("Transfer metadata fields do not match version 2.")
    if (
        raw.get("schema") != HEARTH_TRANSFER_SCHEMA
        or type(raw.get("schema_version")) is not int
        or raw.get("schema_version") != HEARTH_TRANSFER_VERSION
    ):
        raise HearthTransferError("Transfer payload schema is unsupported.")
    return raw


def open_hearth_transfer_payload(
    payload: bytes,
    *,
    identity_descriptor: ResidentIdentityDescriptor,
) -> OpenedHearthTransfer:
    """Validate an opened transfer and return its key only in memory."""

    descriptor = ResidentIdentityDescriptor.from_dict(identity_descriptor.to_dict())
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as transfer:
            metadata = _read_metadata(transfer)
            actor_id = metadata.get("actor_id")
            hearth_shard_id = metadata.get("hearth_shard_id")
            generation = metadata.get("runtime_generation")
            archive_size = metadata.get("archive_size")
            archive_sha256 = metadata.get("archive_sha256")
            if (
                actor_id != descriptor.actor_id
                or hearth_shard_id != descriptor.hearth_shard_id
                or metadata.get("identity_key_id") != descriptor.identity_key_id
            ):
                raise HearthTransferError(
                    "Transfer does not match the reviewed resident identity card."
                )
            if (
                isinstance(generation, bool)
                or not isinstance(generation, int)
                or generation < 1
                or generation > (2**63) - 1
            ):
                raise HearthTransferError("Transfer runtime generation is invalid.")
            if (
                isinstance(archive_size, bool)
                or not isinstance(archive_size, int)
                or archive_size < 0
                or archive_size > _MAX_ARCHIVE_BYTES
            ):
                raise HearthTransferError("Transfer archive size is invalid.")
            if (
                not isinstance(archive_sha256, str)
                or len(archive_sha256) != 64
                or any(char not in "0123456789abcdef" for char in archive_sha256)
            ):
                raise HearthTransferError("Transfer archive hash is invalid.")
            archive_info = transfer.getinfo(HEARTH_TRANSFER_ARCHIVE)
            key_info = transfer.getinfo(HEARTH_TRANSFER_IDENTITY_KEY)
            handoff_info = transfer.getinfo(HEARTH_TRANSFER_HANDOFF)
            if archive_info.file_size != archive_size:
                raise HearthTransferError(
                    "Transfer archive size does not match its metadata."
                )
            if key_info.file_size != 32:
                raise HearthTransferError(
                    "Transfer resident identity key has the wrong size."
                )
            if handoff_info.file_size > _MAX_METADATA_BYTES:
                raise HearthTransferError("Transfer handoff document is too large.")
            hearth_archive = transfer.read(HEARTH_TRANSFER_ARCHIVE)
            if hashlib.sha256(hearth_archive).hexdigest() != archive_sha256:
                raise HearthTransferError(
                    "Transfer archive failed its integrity check."
                )
            try:
                identity_private_key = Ed25519PrivateKey.from_private_bytes(
                    transfer.read(HEARTH_TRANSFER_IDENTITY_KEY)
                )
            except ValueError as exc:
                raise HearthTransferError(
                    "Transfer resident identity key is invalid."
                ) from exc
            handoff = decode_hearth_handoff_authorization(
                transfer.read(HEARTH_TRANSFER_HANDOFF),
                identity_descriptor=descriptor,
            )
    except zipfile.BadZipFile as exc:
        raise HearthTransferError("Transfer payload is not a valid archive.") from exc

    if (
        encoded_identity_public_key(identity_private_key.public_key())
        != descriptor.identity_public_key
    ):
        raise HearthTransferError(
            "Transfer resident identity key does not match its public card."
        )
    if (
        handoff.actor_id != actor_id
        or handoff.hearth_shard_id != hearth_shard_id
        or handoff.source_generation != generation
    ):
        raise HearthTransferError(
            "Transfer handoff does not match its hearth generation."
        )
    return OpenedHearthTransfer(
        archive=hearth_archive,
        identity_private_key=identity_private_key,
        actor_id=actor_id,
        hearth_shard_id=hearth_shard_id,
        runtime_generation=generation,
        handoff_authorization=handoff,
    )
