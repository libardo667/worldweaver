# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cryptographic protocol for one resident runtime generation.

This module defines and verifies portable protocol objects. It does not decide
whether an actor key is admitted, store nonces, or load resident private keys.
Those belong to the city authority boundary and the private hearth respectively.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import re
import secrets
import time
from typing import Any, Iterable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

RESIDENT_CERTIFICATE_HEADER = "X-WW-Resident-Certificate"
RESIDENT_TIMESTAMP_HEADER = "X-WW-Resident-Timestamp"
RESIDENT_NONCE_HEADER = "X-WW-Resident-Nonce"
RESIDENT_SIGNATURE_HEADER = "X-WW-Resident-Signature"

CERTIFICATE_SCHEMA = "worldweaver.resident-runtime-certificate"
CERTIFICATE_VERSION = 1
DEFAULT_MAX_CLOCK_SKEW_SECONDS = 300
MAX_CERTIFICATE_LIFETIME_SECONDS = 24 * 60 * 60
MAX_RUNTIME_GENERATION = (2**63) - 1

_CERTIFICATE_FIELDS = {
    "schema",
    "schema_version",
    "certificate_id",
    "actor_id",
    "hearth_shard_id",
    "runtime_generation",
    "identity_key_id",
    "runtime_public_key",
    "audience",
    "scopes",
    "issued_at",
    "expires_at",
    "identity_signature",
}
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SCOPE_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ResidentProtocolError(ValueError):
    """A resident certificate or signed request is invalid."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    raw = str(value or "").strip()
    if not _BASE64URL_RE.fullmatch(raw):
        raise ResidentProtocolError("Invalid base64 value.")
    try:
        return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (TypeError, ValueError) as exc:
        raise ResidentProtocolError("Invalid base64 value.") from exc


def encoded_public_key(key: Ed25519PublicKey) -> str:
    """Return the protocol encoding for an Ed25519 public key."""

    return _encode(key.public_bytes_raw())


def identity_key_id(public_key: str) -> str:
    """Return a stable public fingerprint without exposing private material."""

    key_bytes = _decode(public_key)
    if len(key_bytes) != 32:
        raise ResidentProtocolError("Resident identity public key is invalid.")
    return f"ed25519:{hashlib.sha256(key_bytes).hexdigest()[:32]}"


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(payload),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _certificate_unsigned_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "identity_signature"}


def _clean_scopes(scopes: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(sorted(set(str(scope or "").strip() for scope in scopes)))
    if not normalized or len(normalized) > 32:
        raise ResidentProtocolError("Certificate must contain between one and 32 scopes.")
    if any(not _SCOPE_RE.fullmatch(scope) for scope in normalized):
        raise ResidentProtocolError("Certificate contains an invalid scope.")
    return normalized


@dataclass(frozen=True, slots=True)
class ResidentRuntimeCertificate:
    certificate_id: str
    actor_id: str
    hearth_shard_id: str
    runtime_generation: int
    identity_key_id: str
    runtime_public_key: str
    audience: str
    scopes: tuple[str, ...]
    issued_at: int
    expires_at: int
    identity_signature: str
    schema: str = CERTIFICATE_SCHEMA
    schema_version: int = CERTIFICATE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "certificate_id": self.certificate_id,
            "actor_id": self.actor_id,
            "hearth_shard_id": self.hearth_shard_id,
            "runtime_generation": self.runtime_generation,
            "identity_key_id": self.identity_key_id,
            "runtime_public_key": self.runtime_public_key,
            "audience": self.audience,
            "scopes": list(self.scopes),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "identity_signature": self.identity_signature,
        }

    def encode_header(self) -> str:
        return _encode(_canonical_json(self.to_dict()))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ResidentRuntimeCertificate":
        if not isinstance(raw, Mapping):
            raise ResidentProtocolError("Resident certificate must be an object.")
        unknown = set(raw) - _CERTIFICATE_FIELDS
        missing = _CERTIFICATE_FIELDS - set(raw)
        if unknown or missing:
            raise ResidentProtocolError("Resident certificate fields do not match version 1.")
        if raw.get("schema") != CERTIFICATE_SCHEMA or raw.get("schema_version") != CERTIFICATE_VERSION:
            raise ResidentProtocolError("Resident certificate schema is unsupported.")

        certificate_id = str(raw.get("certificate_id") or "").strip()
        actor_id = str(raw.get("actor_id") or "").strip()
        hearth_shard_id = str(raw.get("hearth_shard_id") or "").strip()
        audience = str(raw.get("audience") or "").strip()
        identity_id = str(raw.get("identity_key_id") or "").strip()
        runtime_key = str(raw.get("runtime_public_key") or "").strip()
        signature = str(raw.get("identity_signature") or "").strip()
        for value, label in (
            (certificate_id, "certificate_id"),
            (actor_id, "actor_id"),
            (hearth_shard_id, "hearth_shard_id"),
            (audience, "audience"),
            (identity_id, "identity_key_id"),
        ):
            if not _TOKEN_RE.fullmatch(value):
                raise ResidentProtocolError(f"Resident certificate {label} is invalid.")
        try:
            runtime_bytes = _decode(runtime_key)
            signature_bytes = _decode(signature)
        except ResidentProtocolError:
            raise
        if len(runtime_bytes) != 32 or len(signature_bytes) != 64:
            raise ResidentProtocolError("Resident certificate key or signature is invalid.")

        generation = raw.get("runtime_generation")
        issued_at = raw.get("issued_at")
        expires_at = raw.get("expires_at")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1 or generation > MAX_RUNTIME_GENERATION:
            raise ResidentProtocolError("Resident certificate generation is invalid.")
        if isinstance(issued_at, bool) or not isinstance(issued_at, int):
            raise ResidentProtocolError("Resident certificate issued_at is invalid.")
        if isinstance(expires_at, bool) or not isinstance(expires_at, int):
            raise ResidentProtocolError("Resident certificate expires_at is invalid.")
        if expires_at <= issued_at or expires_at - issued_at > MAX_CERTIFICATE_LIFETIME_SECONDS:
            raise ResidentProtocolError("Resident certificate lifetime is invalid.")
        scopes_raw = raw.get("scopes")
        if not isinstance(scopes_raw, list):
            raise ResidentProtocolError("Resident certificate scopes must be a list.")
        scopes = _clean_scopes(scopes_raw)
        if list(scopes_raw) != list(scopes):
            raise ResidentProtocolError("Resident certificate scopes must be sorted and unique.")
        return cls(
            certificate_id=certificate_id,
            actor_id=actor_id,
            hearth_shard_id=hearth_shard_id,
            runtime_generation=generation,
            identity_key_id=identity_id,
            runtime_public_key=runtime_key,
            audience=audience,
            scopes=scopes,
            issued_at=issued_at,
            expires_at=expires_at,
            identity_signature=signature,
        )

    @classmethod
    def decode_header(cls, value: str) -> "ResidentRuntimeCertificate":
        try:
            raw = json.loads(_decode(value))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ResidentProtocolError("Resident certificate header is invalid.") from exc
        return cls.from_dict(raw)


def issue_runtime_certificate(
    *,
    identity_private_key: Ed25519PrivateKey,
    runtime_public_key: Ed25519PublicKey,
    actor_id: str,
    hearth_shard_id: str,
    runtime_generation: int,
    audience: str,
    scopes: Iterable[str],
    issued_at: int | None = None,
    expires_at: int | None = None,
    certificate_id: str | None = None,
) -> ResidentRuntimeCertificate:
    """Sign one bounded runtime key with the stable resident identity key."""

    now = int(time.time()) if issued_at is None else int(issued_at)
    expiry = now + 3600 if expires_at is None else int(expires_at)
    identity_public = encoded_public_key(identity_private_key.public_key())
    unsigned = {
        "schema": CERTIFICATE_SCHEMA,
        "schema_version": CERTIFICATE_VERSION,
        "certificate_id": str(certificate_id or secrets.token_urlsafe(18)).strip(),
        "actor_id": str(actor_id or "").strip(),
        "hearth_shard_id": str(hearth_shard_id or "").strip(),
        "runtime_generation": runtime_generation,
        "identity_key_id": identity_key_id(identity_public),
        "runtime_public_key": encoded_public_key(runtime_public_key),
        "audience": str(audience or "").strip(),
        "scopes": list(_clean_scopes(scopes)),
        "issued_at": now,
        "expires_at": expiry,
    }
    signature = _encode(identity_private_key.sign(_canonical_json(unsigned)))
    return ResidentRuntimeCertificate.from_dict({**unsigned, "identity_signature": signature})


def verify_runtime_certificate(
    certificate: ResidentRuntimeCertificate,
    *,
    identity_public_key: str,
    expected_actor_id: str,
    expected_runtime_generation: int,
    expected_audience: str,
    required_scope: str,
    now: int | None = None,
    max_clock_skew_seconds: int = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
) -> None:
    """Verify identity signature, generation, audience, scope, and lifetime."""

    current_time = int(time.time()) if now is None else int(now)
    if certificate.actor_id != str(expected_actor_id or "").strip():
        raise ResidentProtocolError("Resident certificate actor does not match.")
    if certificate.runtime_generation != int(expected_runtime_generation):
        raise ResidentProtocolError("Resident certificate generation does not match.")
    if certificate.audience != str(expected_audience or "").strip():
        raise ResidentProtocolError("Resident certificate audience does not match.")
    if str(required_scope or "").strip() not in certificate.scopes:
        raise ResidentProtocolError("Resident certificate does not grant this scope.")
    if certificate.issued_at > current_time + max_clock_skew_seconds:
        raise ResidentProtocolError("Resident certificate is not active yet.")
    if certificate.expires_at < current_time:
        raise ResidentProtocolError("Resident certificate has expired.")
    if certificate.identity_key_id != identity_key_id(identity_public_key):
        raise ResidentProtocolError("Resident certificate identity key does not match.")
    try:
        Ed25519PublicKey.from_public_bytes(_decode(identity_public_key)).verify(
            _decode(certificate.identity_signature),
            _canonical_json(_certificate_unsigned_payload(certificate.to_dict())),
        )
    except (ValueError, InvalidSignature) as exc:
        raise ResidentProtocolError("Resident certificate signature is invalid.") from exc


def _canonical_request(
    *,
    method: str,
    target: str,
    body: bytes,
    timestamp: str,
    nonce: str,
    certificate_header: str,
) -> bytes:
    return "\n".join(
        (
            method.upper(),
            target,
            timestamp,
            nonce,
            hashlib.sha256(body).hexdigest(),
            hashlib.sha256(certificate_header.encode("ascii")).hexdigest(),
        )
    ).encode("utf-8")


def signed_resident_request_headers(
    *,
    runtime_private_key: Ed25519PrivateKey,
    certificate: ResidentRuntimeCertificate,
    method: str,
    target: str,
    body: bytes = b"",
    timestamp: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    """Sign an exact request with the key named by a runtime certificate."""

    signed_at = str(int(time.time()) if timestamp is None else int(timestamp))
    request_nonce = str(nonce or secrets.token_urlsafe(18)).strip()
    certificate_header = certificate.encode_header()
    signature = runtime_private_key.sign(
        _canonical_request(
            method=method,
            target=target,
            body=body,
            timestamp=signed_at,
            nonce=request_nonce,
            certificate_header=certificate_header,
        )
    )
    return {
        RESIDENT_CERTIFICATE_HEADER: certificate_header,
        RESIDENT_TIMESTAMP_HEADER: signed_at,
        RESIDENT_NONCE_HEADER: request_nonce,
        RESIDENT_SIGNATURE_HEADER: _encode(signature),
    }


@dataclass(frozen=True, slots=True)
class VerifiedResidentRequest:
    actor_id: str
    hearth_shard_id: str
    runtime_generation: int
    certificate_id: str
    identity_key_id: str
    audience: str
    scope: str
    signed_at: int
    nonce: str


def verify_resident_request(
    *,
    identity_public_key: str,
    expected_actor_id: str,
    expected_runtime_generation: int,
    expected_audience: str,
    required_scope: str,
    method: str,
    target: str,
    body: bytes,
    headers: Mapping[str, str],
    now: int | None = None,
    max_clock_skew_seconds: int = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
) -> VerifiedResidentRequest:
    """Verify a certificate and the exact request signed by its runtime key.

    Replay storage is intentionally outside this pure function. A caller must
    atomically consume ``(certificate_id, nonce)`` before running the command.
    """

    certificate_header = str(headers.get(RESIDENT_CERTIFICATE_HEADER) or "").strip()
    timestamp = str(headers.get(RESIDENT_TIMESTAMP_HEADER) or "").strip()
    nonce = str(headers.get(RESIDENT_NONCE_HEADER) or "").strip()
    signature = str(headers.get(RESIDENT_SIGNATURE_HEADER) or "").strip()
    if not certificate_header or not timestamp or not nonce or not signature:
        raise ResidentProtocolError("Resident request headers are incomplete.")
    if not _TOKEN_RE.fullmatch(nonce):
        raise ResidentProtocolError("Resident request nonce is invalid.")
    try:
        signed_at = int(timestamp)
    except ValueError as exc:
        raise ResidentProtocolError("Resident request timestamp is invalid.") from exc
    current_time = int(time.time()) if now is None else int(now)
    if abs(current_time - signed_at) > max_clock_skew_seconds:
        raise ResidentProtocolError("Resident request timestamp is outside the allowed window.")

    certificate = ResidentRuntimeCertificate.decode_header(certificate_header)
    verify_runtime_certificate(
        certificate,
        identity_public_key=identity_public_key,
        expected_actor_id=expected_actor_id,
        expected_runtime_generation=expected_runtime_generation,
        expected_audience=expected_audience,
        required_scope=required_scope,
        now=current_time,
        max_clock_skew_seconds=max_clock_skew_seconds,
    )
    if signed_at < certificate.issued_at - max_clock_skew_seconds or signed_at > certificate.expires_at:
        raise ResidentProtocolError("Resident request falls outside its certificate lifetime.")
    try:
        Ed25519PublicKey.from_public_bytes(_decode(certificate.runtime_public_key)).verify(
            _decode(signature),
            _canonical_request(
                method=method,
                target=target,
                body=body,
                timestamp=timestamp,
                nonce=nonce,
                certificate_header=certificate_header,
            ),
        )
    except (ValueError, InvalidSignature) as exc:
        raise ResidentProtocolError("Resident request signature is invalid.") from exc
    return VerifiedResidentRequest(
        actor_id=certificate.actor_id,
        hearth_shard_id=certificate.hearth_shard_id,
        runtime_generation=certificate.runtime_generation,
        certificate_id=certificate.certificate_id,
        identity_key_id=certificate.identity_key_id,
        audience=certificate.audience,
        scope=str(required_scope or "").strip(),
        signed_at=signed_at,
        nonce=nonce,
    )
