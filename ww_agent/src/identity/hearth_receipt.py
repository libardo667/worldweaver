# SPDX-License-Identifier: AGPL-3.0-or-later
"""Host-witnessed receipts for the two durable halves of a hearth handoff.

A source receipt says its authorized generation is retired. A destination
receipt says the next generation is active. Neither receipt permits deletion.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Literal, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.identity.hearth_handoff import HearthHandoffAuthorization
from src.identity.host_witness import HostWitnessDescriptor

HEARTH_RECEIPT_SCHEMA = "worldweaver.hearth-handoff-receipt"
HEARTH_RECEIPT_VERSION = 1
HEARTH_RETIREMENT_RECEIPT_FILENAME = "hearth_retirement_receipt.json"
HEARTH_ACTIVATION_RECEIPT_FILENAME = "hearth_activation_receipt.json"

ReceiptPhase = Literal["source_retired", "destination_activated"]
_FIELDS = {
    "schema",
    "schema_version",
    "phase",
    "transfer_id",
    "actor_id",
    "hearth_shard_id",
    "runtime_generation",
    "witness_id",
    "witness_key_id",
    "witness_signature",
}
_UNSIGNED_FIELDS = tuple(sorted(_FIELDS - {"witness_signature"}))
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_RECEIPT_BYTES = 64 * 1024


class HearthReceiptError(ValueError):
    """A source-retirement or destination-activation receipt is invalid."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: Any, *, label: str, expected_size: int) -> bytes:
    encoded = str(value or "").strip()
    if (
        not isinstance(value, str)
        or value != encoded
        or not _BASE64URL_RE.fullmatch(encoded)
    ):
        raise HearthReceiptError(f"Hearth receipt {label} is invalid.")
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (TypeError, ValueError, binascii.Error) as exc:
        raise HearthReceiptError(f"Hearth receipt {label} is invalid.") from exc
    if len(decoded) != expected_size:
        raise HearthReceiptError(f"Hearth receipt {label} has the wrong size.")
    return decoded


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _expected_witness(
    handoff: HearthHandoffAuthorization,
    phase: ReceiptPhase,
) -> tuple[str, str, int]:
    if phase == "source_retired":
        return (
            handoff.source_witness_id,
            handoff.source_witness_key_id,
            handoff.source_generation,
        )
    if phase == "destination_activated":
        return (
            handoff.destination_witness_id,
            handoff.destination_witness_key_id,
            handoff.destination_generation,
        )
    raise HearthReceiptError("Hearth receipt phase is unsupported.")


@dataclass(frozen=True, slots=True)
class HearthHandoffReceipt:
    phase: ReceiptPhase
    transfer_id: str
    actor_id: str
    hearth_shard_id: str
    runtime_generation: int
    witness_id: str
    witness_key_id: str
    witness_signature: str
    schema: str = HEARTH_RECEIPT_SCHEMA
    schema_version: int = HEARTH_RECEIPT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "phase": self.phase,
            "transfer_id": self.transfer_id,
            "actor_id": self.actor_id,
            "hearth_shard_id": self.hearth_shard_id,
            "runtime_generation": self.runtime_generation,
            "witness_id": self.witness_id,
            "witness_key_id": self.witness_key_id,
            "witness_signature": self.witness_signature,
        }

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
        *,
        handoff: HearthHandoffAuthorization,
        witness: HostWitnessDescriptor,
    ) -> "HearthHandoffReceipt":
        if not isinstance(raw, Mapping) or set(raw) != _FIELDS:
            raise HearthReceiptError("Hearth receipt fields do not match version 1.")
        if (
            raw.get("schema") != HEARTH_RECEIPT_SCHEMA
            or type(raw.get("schema_version")) is not int
            or raw.get("schema_version") != HEARTH_RECEIPT_VERSION
        ):
            raise HearthReceiptError("Hearth receipt schema is unsupported.")
        phase = raw.get("phase")
        if phase not in {"source_retired", "destination_activated"}:
            raise HearthReceiptError("Hearth receipt phase is unsupported.")
        expected_id, expected_key_id, expected_generation = _expected_witness(
            handoff,
            phase,
        )
        if (
            raw.get("transfer_id") != handoff.transfer_id
            or raw.get("actor_id") != handoff.actor_id
            or raw.get("hearth_shard_id") != handoff.hearth_shard_id
            or raw.get("runtime_generation") != expected_generation
        ):
            raise HearthReceiptError(
                "Hearth receipt does not match its authorized handoff."
            )
        if (
            witness.witness_id != expected_id
            or witness.key_id != expected_key_id
            or raw.get("witness_id") != expected_id
            or raw.get("witness_key_id") != expected_key_id
        ):
            raise HearthReceiptError("Hearth receipt witness is not authorized.")
        signature = str(raw.get("witness_signature") or "").strip()
        signature_bytes = _decode(
            signature,
            label="witness signature",
            expected_size=64,
        )
        unsigned = {field: raw[field] for field in _UNSIGNED_FIELDS}
        try:
            witness.public_key_object.verify(
                signature_bytes,
                _canonical_json(unsigned),
            )
        except (InvalidSignature, ValueError) as exc:
            raise HearthReceiptError(
                "Hearth receipt witness signature is invalid."
            ) from exc
        return cls(
            phase=phase,
            transfer_id=handoff.transfer_id,
            actor_id=handoff.actor_id,
            hearth_shard_id=handoff.hearth_shard_id,
            runtime_generation=expected_generation,
            witness_id=expected_id,
            witness_key_id=expected_key_id,
            witness_signature=signature,
        )


def create_hearth_handoff_receipt(
    handoff: HearthHandoffAuthorization,
    *,
    phase: ReceiptPhase,
    witness: HostWitnessDescriptor,
    witness_private_key: Ed25519PrivateKey,
) -> HearthHandoffReceipt:
    """Sign one narrow receipt with the host witness named by the resident."""

    expected_id, expected_key_id, generation = _expected_witness(handoff, phase)
    if witness.witness_id != expected_id or witness.key_id != expected_key_id:
        raise HearthReceiptError("Hearth receipt witness is not authorized.")
    if witness_private_key.public_key().public_bytes_raw() != (
        witness.public_key_object.public_bytes_raw()
    ):
        raise HearthReceiptError(
            "Hearth receipt private key does not match its witness descriptor."
        )
    unsigned: dict[str, Any] = {
        "schema": HEARTH_RECEIPT_SCHEMA,
        "schema_version": HEARTH_RECEIPT_VERSION,
        "phase": phase,
        "transfer_id": handoff.transfer_id,
        "actor_id": handoff.actor_id,
        "hearth_shard_id": handoff.hearth_shard_id,
        "runtime_generation": generation,
        "witness_id": expected_id,
        "witness_key_id": expected_key_id,
    }
    return HearthHandoffReceipt.from_dict(
        {
            **unsigned,
            "witness_signature": _encode(
                witness_private_key.sign(_canonical_json(unsigned))
            ),
        },
        handoff=handoff,
        witness=witness,
    )


def encode_hearth_handoff_receipt(
    receipt: HearthHandoffReceipt,
    *,
    handoff: HearthHandoffAuthorization,
    witness: HostWitnessDescriptor,
) -> bytes:
    verified = HearthHandoffReceipt.from_dict(
        receipt.to_dict(),
        handoff=handoff,
        witness=witness,
    )
    return (json.dumps(verified.to_dict(), indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def decode_hearth_handoff_receipt(
    encoded: bytes,
    *,
    handoff: HearthHandoffAuthorization,
    witness: HostWitnessDescriptor,
) -> HearthHandoffReceipt:
    if len(encoded) > _MAX_RECEIPT_BYTES:
        raise HearthReceiptError("Hearth receipt is too large.")
    try:
        raw = json.loads(bytes(encoded))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HearthReceiptError("Hearth receipt is not valid UTF-8 JSON.") from exc
    return HearthHandoffReceipt.from_dict(raw, handoff=handoff, witness=witness)


def load_hearth_handoff_receipt(
    path: str | Path,
    *,
    handoff: HearthHandoffAuthorization,
    witness: HostWitnessDescriptor,
) -> HearthHandoffReceipt:
    receipt_path = Path(path).expanduser()
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise HearthReceiptError(f"Hearth receipt is missing or unsafe: {receipt_path}")
    try:
        encoded = receipt_path.read_bytes()
    except OSError as exc:
        raise HearthReceiptError(
            f"Could not read hearth receipt: {receipt_path}"
        ) from exc
    return decode_hearth_handoff_receipt(
        encoded,
        handoff=handoff,
        witness=witness,
    )


def write_hearth_handoff_receipt(
    path: str | Path,
    receipt: HearthHandoffReceipt,
    *,
    handoff: HearthHandoffAuthorization,
    witness: HostWitnessDescriptor,
) -> None:
    """Create one owner-only receipt file without replacing evidence."""

    receipt_path = Path(path)
    encoded = encode_hearth_handoff_receipt(
        receipt,
        handoff=handoff,
        witness=witness,
    )
    if receipt_path.exists() or receipt_path.is_symlink():
        raise HearthReceiptError(
            f"Refusing to replace existing hearth receipt: {receipt_path}"
        )
    if not receipt_path.parent.is_dir() or receipt_path.parent.is_symlink():
        raise HearthReceiptError(
            f"Hearth receipt parent is missing or unsafe: {receipt_path.parent}"
        )
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=receipt_path.parent,
            prefix=f".{receipt_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, receipt_path)
        receipt_path.chmod(0o600)
    except OSError as exc:
        raise HearthReceiptError(f"Could not write hearth receipt: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
