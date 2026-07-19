# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Node-owned identities and signed federation HTTP requests."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

NODE_ID_HEADER = "X-WW-Node-ID"
NODE_TIMESTAMP_HEADER = "X-WW-Timestamp"
NODE_NONCE_HEADER = "X-WW-Nonce"
NODE_SIGNATURE_HEADER = "X-WW-Signature"
NODE_PUBLIC_KEY_HEADER = "X-WW-Node-Public-Key"
DEFAULT_MAX_CLOCK_SKEW_SECONDS = 300


class NodeSignatureError(ValueError):
    """A node identity or signed request is malformed or invalid."""


@dataclass(frozen=True)
class AuthenticatedNode:
    """The node proven by a signed request, or a temporary legacy token."""

    node_id: str | None
    public_key: str | None
    method: str


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    raw = str(value or "").strip()
    try:
        return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (ValueError, TypeError) as exc:
        raise NodeSignatureError("Invalid base64 value.") from exc


def _canonical_request(
    *,
    method: str,
    path: str,
    body: bytes,
    timestamp: str,
    nonce: str,
) -> bytes:
    body_digest = hashlib.sha256(body).hexdigest()
    return "\n".join((method.upper(), path, timestamp, nonce, body_digest)).encode("utf-8")


def generate_node_identity(
    *,
    private_key_path: Path,
    descriptor_path: Path,
    node_id: str,
    shard_type: str,
    city_id: str | None,
) -> dict[str, object]:
    """Create one private node key and its safe-to-share public descriptor."""
    if private_key_path.exists():
        raise FileExistsError(f"Node private key already exists: {private_key_path}")
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes_raw()
    public_key = _encode(private_key.public_key().public_bytes_raw())
    descriptor = write_public_descriptor(
        descriptor_path=descriptor_path,
        node_id=node_id,
        shard_type=shard_type,
        city_id=city_id,
        public_key=public_key,
    )

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_path.parent.chmod(0o700)
    private_key_path.write_text(f"{_encode(private_bytes)}\n", encoding="utf-8")
    private_key_path.chmod(0o600)
    return descriptor


def write_public_descriptor(
    *,
    descriptor_path: Path,
    node_id: str,
    shard_type: str,
    city_id: str | None,
    public_key: str,
) -> dict[str, object]:
    """Write the public half of a node identity without exposing its key file."""
    descriptor: dict[str, object] = {
        "schema": "worldweaver.node",
        "schema_version": 1,
        "node_id": node_id,
        "shard_type": shard_type,
        "public_key": public_key,
    }
    if city_id:
        descriptor["city_id"] = city_id
    descriptor_path.write_text(f"{json.dumps(descriptor, indent=2, sort_keys=True)}\n", encoding="utf-8")
    return descriptor


def load_private_key(path: str | Path) -> Ed25519PrivateKey:
    key_path = Path(path).expanduser()
    try:
        private_bytes = _decode(key_path.read_text(encoding="utf-8"))
        return Ed25519PrivateKey.from_private_bytes(private_bytes)
    except (OSError, ValueError) as exc:
        raise NodeSignatureError(f"Could not load node private key: {key_path}") from exc


def public_key_for_private_key(path: str | Path) -> str:
    return _encode(load_private_key(path).public_key().public_bytes_raw())


def signed_request_headers(
    *,
    node_id: str,
    private_key_path: str | Path,
    method: str,
    path: str,
    body: bytes = b"",
    timestamp: int | None = None,
    nonce: str | None = None,
    include_public_key: bool = False,
) -> dict[str, str]:
    signed_at = str(int(time.time()) if timestamp is None else int(timestamp))
    request_nonce = str(nonce or secrets.token_urlsafe(18)).strip()
    if not node_id.strip() or not request_nonce:
        raise NodeSignatureError("Node ID and request nonce are required.")
    private_key = load_private_key(private_key_path)
    signature = private_key.sign(
        _canonical_request(
            method=method,
            path=path,
            body=body,
            timestamp=signed_at,
            nonce=request_nonce,
        )
    )
    headers = {
        NODE_ID_HEADER: node_id.strip(),
        NODE_TIMESTAMP_HEADER: signed_at,
        NODE_NONCE_HEADER: request_nonce,
        NODE_SIGNATURE_HEADER: _encode(signature),
    }
    if include_public_key:
        headers[NODE_PUBLIC_KEY_HEADER] = _encode(private_key.public_key().public_bytes_raw())
    return headers


def verify_signed_request(
    *,
    public_key: str,
    method: str,
    path: str,
    body: bytes,
    headers: Mapping[str, str],
    now: int | None = None,
    max_clock_skew_seconds: int = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
) -> tuple[str, str]:
    """Verify one request and return its timestamp and nonce."""
    timestamp = str(headers.get(NODE_TIMESTAMP_HEADER) or "").strip()
    nonce = str(headers.get(NODE_NONCE_HEADER) or "").strip()
    signature = str(headers.get(NODE_SIGNATURE_HEADER) or "").strip()
    if not timestamp or not nonce or not signature:
        raise NodeSignatureError("Signed node request headers are incomplete.")
    try:
        signed_at = int(timestamp)
    except ValueError as exc:
        raise NodeSignatureError("Signed request timestamp is invalid.") from exc
    current_time = int(time.time()) if now is None else int(now)
    if abs(current_time - signed_at) > max_clock_skew_seconds:
        raise NodeSignatureError("Signed request timestamp is outside the allowed window.")
    try:
        Ed25519PublicKey.from_public_bytes(_decode(public_key)).verify(
            _decode(signature),
            _canonical_request(
                method=method,
                path=path,
                body=body,
                timestamp=timestamp,
                nonce=nonce,
            ),
        )
    except (ValueError, InvalidSignature) as exc:
        raise NodeSignatureError("Node request signature is invalid.") from exc
    return timestamp, nonce
