# SPDX-License-Identifier: AGPL-3.0-or-later
"""Authenticated encryption for a stopped hearth payload.

The resident identity signs the encrypted envelope. A separate X25519 key lets
one reviewed temporary host decrypt it. This module does not decide whether a
host is authorized, store either private key, or alter hearth generations.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import secrets
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

HEARTH_ENVELOPE_SCHEMA = "worldweaver.encrypted-hearth"
HEARTH_ENVELOPE_VERSION = 1
HEARTH_ENVELOPE_CIPHER = "X25519-HKDF-SHA256+A256GCM+Ed25519"

_MAX_PAYLOAD_BYTES = 64 * 1024 * 1024 * 1024
_MAX_ENVELOPE_BYTES = ((_MAX_PAYLOAD_BYTES + 16) * 4 // 3) + (1024 * 1024)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_ENVELOPE_FIELDS = {
    "schema",
    "schema_version",
    "cipher",
    "actor_id",
    "hearth_shard_id",
    "runtime_generation",
    "resident_identity_public_key",
    "recipient_key_id",
    "ephemeral_public_key",
    "nonce",
    "ciphertext",
    "resident_signature",
}
_HEADER_FIELDS = (
    "schema",
    "schema_version",
    "cipher",
    "actor_id",
    "hearth_shard_id",
    "runtime_generation",
    "resident_identity_public_key",
    "recipient_key_id",
    "ephemeral_public_key",
    "nonce",
)
_HKDF_INFO = b"worldweaver.encrypted-hearth.v1"


class HearthEnvelopeError(ValueError):
    """An encrypted hearth envelope is malformed, untrusted, or unreadable."""


@dataclass(frozen=True, slots=True)
class DecryptedHearthEnvelope:
    payload: bytes
    actor_id: str
    hearth_shard_id: str
    runtime_generation: int
    resident_identity_public_key: str
    recipient_key_id: str
    payload_sha256: str


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: Any, *, label: str, expected_size: int | None = None) -> bytes:
    encoded = str(value or "").strip()
    if not _BASE64URL_RE.fullmatch(encoded):
        raise HearthEnvelopeError(f"Encrypted hearth {label} is invalid.")
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (TypeError, ValueError, binascii.Error) as exc:
        raise HearthEnvelopeError(f"Encrypted hearth {label} is invalid.") from exc
    if expected_size is not None and len(decoded) != expected_size:
        raise HearthEnvelopeError(f"Encrypted hearth {label} has the wrong size.")
    return decoded


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def encoded_transport_public_key(key: X25519PublicKey) -> str:
    """Return the safe-to-share encoding of one host transport public key."""

    return _encode(key.public_bytes_raw())


def encoded_resident_identity_public_key(key: Ed25519PublicKey) -> str:
    """Return the safe-to-share encoding of one resident identity public key."""

    return _encode(key.public_bytes_raw())


def transport_key_id(public_key: str | X25519PublicKey) -> str:
    """Return a short public fingerprint for a host transport key."""

    encoded = (
        encoded_transport_public_key(public_key)
        if isinstance(public_key, X25519PublicKey)
        else str(public_key or "").strip()
    )
    raw = _decode(encoded, label="recipient public key", expected_size=32)
    return f"x25519:{hashlib.sha256(raw).hexdigest()[:32]}"


def load_transport_private_key(path: str | Path) -> X25519PrivateKey:
    """Load one host-owned receiver key from a regular file."""

    key_path = Path(path).expanduser()
    if not key_path.is_file() or key_path.is_symlink():
        raise HearthEnvelopeError(
            f"Hearth transport private key is missing or unsafe: {key_path}"
        )
    try:
        encoded = key_path.read_bytes()
        if len(encoded) > 256:
            raise HearthEnvelopeError("Hearth transport private key is too large.")
        raw = _decode(
            encoded.decode("utf-8").strip(),
            label="private key",
            expected_size=32,
        )
        return X25519PrivateKey.from_private_bytes(raw)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise HearthEnvelopeError(
            f"Could not load hearth transport private key: {key_path}"
        ) from exc


def load_transport_public_key(path: str | Path) -> X25519PublicKey:
    """Load and verify one safe-to-share hearth-host descriptor."""

    descriptor_path = Path(path).expanduser()
    if not descriptor_path.is_file() or descriptor_path.is_symlink():
        raise HearthEnvelopeError(
            f"Hearth transport descriptor is missing or unsafe: {descriptor_path}"
        )
    try:
        encoded = descriptor_path.read_bytes()
        if len(encoded) > 16 * 1024:
            raise HearthEnvelopeError("Hearth transport descriptor is too large.")
        raw = json.loads(encoded)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HearthEnvelopeError(
            f"Could not load hearth transport descriptor: {descriptor_path}"
        ) from exc
    fields = {
        "schema",
        "schema_version",
        "transport_key_id",
        "transport_public_key",
    }
    if not isinstance(raw, dict) or set(raw) != fields:
        raise HearthEnvelopeError(
            "Hearth transport descriptor fields do not match version 1."
        )
    if (
        raw.get("schema") != "worldweaver.hearth-transport"
        or type(raw.get("schema_version")) is not int
        or raw.get("schema_version") != 1
    ):
        raise HearthEnvelopeError("Hearth transport descriptor is unsupported.")
    public_key = str(raw.get("transport_public_key") or "").strip()
    if raw.get("transport_public_key") != public_key:
        raise HearthEnvelopeError("Hearth transport descriptor key is invalid.")
    if raw.get("transport_key_id") != transport_key_id(public_key):
        raise HearthEnvelopeError("Hearth transport descriptor key ID does not match.")
    return X25519PublicKey.from_public_bytes(
        _decode(public_key, label="recipient public key", expected_size=32)
    )


def _derive_content_key(
    *,
    private_key: X25519PrivateKey,
    public_key: X25519PublicKey,
) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_HKDF_INFO,
    ).derive(private_key.exchange(public_key))


def encrypt_hearth_payload(
    payload: bytes,
    *,
    actor_id: str,
    hearth_shard_id: str,
    runtime_generation: int,
    resident_identity_private_key: Ed25519PrivateKey,
    recipient_transport_public_key: X25519PublicKey,
) -> bytes:
    """Encrypt and resident-sign one already-validated stopped hearth payload."""

    content = bytes(payload)
    actor = str(actor_id or "").strip()
    hearth = str(hearth_shard_id or "").strip()
    if len(content) > _MAX_PAYLOAD_BYTES:
        raise HearthEnvelopeError(
            "Stopped hearth payload exceeds the envelope size limit."
        )
    if not _TOKEN_RE.fullmatch(actor):
        raise HearthEnvelopeError("Encrypted hearth actor ID is invalid.")
    if not _TOKEN_RE.fullmatch(hearth):
        raise HearthEnvelopeError("Encrypted hearth shard ID is invalid.")
    if (
        isinstance(runtime_generation, bool)
        or not isinstance(runtime_generation, int)
        or runtime_generation < 1
        or runtime_generation > (2**63) - 1
    ):
        raise HearthEnvelopeError("Encrypted hearth runtime generation is invalid.")

    ephemeral_private = X25519PrivateKey.generate()
    ephemeral_public = ephemeral_private.public_key()
    nonce = secrets.token_bytes(12)
    identity_public = encoded_resident_identity_public_key(
        resident_identity_private_key.public_key()
    )
    header: dict[str, Any] = {
        "schema": HEARTH_ENVELOPE_SCHEMA,
        "schema_version": HEARTH_ENVELOPE_VERSION,
        "cipher": HEARTH_ENVELOPE_CIPHER,
        "actor_id": actor,
        "hearth_shard_id": hearth,
        "runtime_generation": runtime_generation,
        "resident_identity_public_key": identity_public,
        "recipient_key_id": transport_key_id(recipient_transport_public_key),
        "ephemeral_public_key": encoded_transport_public_key(ephemeral_public),
        "nonce": _encode(nonce),
    }
    aad = _canonical_json(header)
    content_key = _derive_content_key(
        private_key=ephemeral_private,
        public_key=recipient_transport_public_key,
    )
    ciphertext = AESGCM(content_key).encrypt(nonce, content, aad)
    signed = {**header, "ciphertext": _encode(ciphertext)}
    signature = resident_identity_private_key.sign(_canonical_json(signed))
    envelope = {**signed, "resident_signature": _encode(signature)}
    return (json.dumps(envelope, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _parse_envelope(encoded_envelope: bytes) -> dict[str, Any]:
    if len(encoded_envelope) > _MAX_ENVELOPE_BYTES:
        raise HearthEnvelopeError("Encrypted hearth envelope exceeds the size limit.")
    try:
        raw = json.loads(bytes(encoded_envelope))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HearthEnvelopeError(
            "Encrypted hearth envelope is not valid UTF-8 JSON."
        ) from exc
    if not isinstance(raw, dict) or set(raw) != _ENVELOPE_FIELDS:
        raise HearthEnvelopeError(
            "Encrypted hearth envelope fields do not match version 1."
        )
    if (
        raw.get("schema") != HEARTH_ENVELOPE_SCHEMA
        or raw.get("schema_version") != HEARTH_ENVELOPE_VERSION
    ):
        raise HearthEnvelopeError("Encrypted hearth envelope schema is unsupported.")
    if raw.get("cipher") != HEARTH_ENVELOPE_CIPHER:
        raise HearthEnvelopeError("Encrypted hearth cipher suite is unsupported.")
    actor = str(raw.get("actor_id") or "").strip()
    hearth = str(raw.get("hearth_shard_id") or "").strip()
    recipient = str(raw.get("recipient_key_id") or "").strip()
    if not _TOKEN_RE.fullmatch(actor) or not _TOKEN_RE.fullmatch(hearth):
        raise HearthEnvelopeError("Encrypted hearth identity is invalid.")
    if not re.fullmatch(r"x25519:[0-9a-f]{32}", recipient):
        raise HearthEnvelopeError("Encrypted hearth recipient key ID is invalid.")
    generation = raw.get("runtime_generation")
    if (
        isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 1
        or generation > (2**63) - 1
    ):
        raise HearthEnvelopeError("Encrypted hearth runtime generation is invalid.")
    _decode(
        raw.get("resident_identity_public_key"),
        label="resident identity public key",
        expected_size=32,
    )
    _decode(
        raw.get("ephemeral_public_key"), label="ephemeral public key", expected_size=32
    )
    _decode(raw.get("nonce"), label="nonce", expected_size=12)
    _decode(raw.get("ciphertext"), label="ciphertext")
    _decode(raw.get("resident_signature"), label="resident signature", expected_size=64)
    return raw


def decrypt_hearth_payload(
    encoded_envelope: bytes,
    *,
    recipient_transport_private_key: X25519PrivateKey,
    expected_resident_identity_public_key: str,
) -> DecryptedHearthEnvelope:
    """Verify and decrypt one envelope for the expected resident identity."""

    raw = _parse_envelope(encoded_envelope)
    expected_identity = str(expected_resident_identity_public_key or "").strip()
    _decode(
        expected_identity,
        label="expected resident identity public key",
        expected_size=32,
    )
    if raw["resident_identity_public_key"] != expected_identity:
        raise HearthEnvelopeError(
            "Encrypted hearth resident identity does not match the expected identity."
        )

    signed = {key: raw[key] for key in (*_HEADER_FIELDS, "ciphertext")}
    try:
        Ed25519PublicKey.from_public_bytes(
            _decode(
                expected_identity,
                label="resident identity public key",
                expected_size=32,
            )
        ).verify(
            _decode(
                raw["resident_signature"], label="resident signature", expected_size=64
            ),
            _canonical_json(signed),
        )
    except (InvalidSignature, ValueError) as exc:
        raise HearthEnvelopeError(
            "Encrypted hearth resident signature is invalid."
        ) from exc

    recipient_public = recipient_transport_private_key.public_key()
    if raw["recipient_key_id"] != transport_key_id(recipient_public):
        raise HearthEnvelopeError(
            "Encrypted hearth was prepared for another host transport key."
        )
    ephemeral_public = X25519PublicKey.from_public_bytes(
        _decode(
            raw["ephemeral_public_key"], label="ephemeral public key", expected_size=32
        )
    )
    content_key = _derive_content_key(
        private_key=recipient_transport_private_key,
        public_key=ephemeral_public,
    )
    header = {key: raw[key] for key in _HEADER_FIELDS}
    try:
        payload = AESGCM(content_key).decrypt(
            _decode(raw["nonce"], label="nonce", expected_size=12),
            _decode(raw["ciphertext"], label="ciphertext"),
            _canonical_json(header),
        )
    except (InvalidTag, ValueError) as exc:
        raise HearthEnvelopeError(
            "Encrypted hearth ciphertext could not be authenticated."
        ) from exc
    digest = hashlib.sha256(payload).hexdigest()
    return DecryptedHearthEnvelope(
        payload=payload,
        actor_id=raw["actor_id"],
        hearth_shard_id=raw["hearth_shard_id"],
        runtime_generation=raw["runtime_generation"],
        resident_identity_public_key=raw["resident_identity_public_key"],
        recipient_key_id=raw["recipient_key_id"],
        payload_sha256=digest,
    )
