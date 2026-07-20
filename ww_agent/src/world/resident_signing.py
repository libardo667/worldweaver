# SPDX-License-Identifier: AGPL-3.0-or-later
"""Issue short-lived resident runtime authority and sign exact city requests.

The long-term resident identity key stays sealed for its current hearth host. It
is opened only to sign a replaceable runtime key, then ordinary requests use the
runtime key. The city must already have admitted the resident's public identity.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
from typing import Callable, Iterable

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.identity.hearth_envelope import load_transport_private_key
from src.identity.hearth_manifest import load_hearth_manifest
from src.identity.resident_identity import (
    encoded_identity_public_key,
    load_resident_identity_descriptor,
    resident_identity_key_id,
)
from src.identity.resident_key_seal import (
    SEALED_RESIDENT_IDENTITY_FILENAME,
    load_resident_key_seal,
    open_sealed_resident_identity_private_key,
)

RESIDENT_CERTIFICATE_HEADER = "X-WW-Resident-Certificate"
RESIDENT_TIMESTAMP_HEADER = "X-WW-Resident-Timestamp"
RESIDENT_NONCE_HEADER = "X-WW-Resident-Nonce"
RESIDENT_SIGNATURE_HEADER = "X-WW-Resident-Signature"

_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_METHOD_RE = re.compile(r"^[A-Z]{1,16}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SCOPE_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")

CERTIFICATE_SCHEMA = "worldweaver.resident-runtime-certificate"
CERTIFICATE_VERSION = 1
MAX_CERTIFICATE_LIFETIME_SECONDS = 24 * 60 * 60
DEFAULT_CERTIFICATE_LIFETIME_SECONDS = 60 * 60
DEFAULT_RESIDENT_RUNTIME_SCOPES = (
    "session.act",
    "session.bootstrap",
    "session.lifecycle",
)


class ResidentSigningError(ValueError):
    """A runtime signer or exact request cannot be represented safely."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _canonical_json(value: dict[str, object]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _clean_scopes(scopes: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(sorted(set(str(scope or "").strip() for scope in scopes)))
    if not normalized or len(normalized) > 32:
        raise ResidentSigningError(
            "Resident certificate must contain between one and 32 scopes."
        )
    if any(not _SCOPE_RE.fullmatch(scope) for scope in normalized):
        raise ResidentSigningError("Resident certificate contains an invalid scope.")
    return normalized


def issue_runtime_certificate_header(
    *,
    identity_private_key: Ed25519PrivateKey,
    runtime_public_key: Ed25519PublicKey,
    actor_id: str,
    hearth_shard_id: str,
    runtime_generation: int,
    audience: str,
    scopes: Iterable[str] = DEFAULT_RESIDENT_RUNTIME_SCOPES,
    issued_at: int | None = None,
    lifetime_seconds: int = DEFAULT_CERTIFICATE_LIFETIME_SECONDS,
) -> tuple[str, int]:
    """Create the engine's version-1 certificate header without importing it."""

    now = int(time.time()) if issued_at is None else int(issued_at)
    lifetime = int(lifetime_seconds)
    actor = str(actor_id or "").strip()
    hearth = str(hearth_shard_id or "").strip()
    target_audience = str(audience or "").strip()
    if any(
        not _TOKEN_RE.fullmatch(value) for value in (actor, hearth, target_audience)
    ):
        raise ResidentSigningError("Resident certificate binding is invalid.")
    if (
        isinstance(runtime_generation, bool)
        or not isinstance(runtime_generation, int)
        or runtime_generation < 1
    ):
        raise ResidentSigningError("Resident certificate generation is invalid.")
    if not 1 <= lifetime <= MAX_CERTIFICATE_LIFETIME_SECONDS:
        raise ResidentSigningError("Resident certificate lifetime is invalid.")
    try:
        runtime_public = runtime_public_key.public_bytes_raw()
    except (AttributeError, TypeError, ValueError) as exc:
        raise ResidentSigningError("Resident runtime public key is invalid.") from exc
    if len(runtime_public) != 32:
        raise ResidentSigningError("Resident runtime public key is invalid.")
    identity_public = encoded_identity_public_key(identity_private_key.public_key())
    unsigned: dict[str, object] = {
        "schema": CERTIFICATE_SCHEMA,
        "schema_version": CERTIFICATE_VERSION,
        "certificate_id": secrets.token_urlsafe(18),
        "actor_id": actor,
        "hearth_shard_id": hearth,
        "runtime_generation": runtime_generation,
        "identity_key_id": resident_identity_key_id(identity_public),
        "runtime_public_key": _encode(runtime_public),
        "audience": target_audience,
        "scopes": list(_clean_scopes(scopes)),
        "issued_at": now,
        "expires_at": now + lifetime,
    }
    payload = {
        **unsigned,
        "identity_signature": _encode(
            identity_private_key.sign(_canonical_json(unsigned))
        ),
    }
    return _encode(_canonical_json(payload)), now + lifetime


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
            method,
            target,
            timestamp,
            nonce,
            hashlib.sha256(body).hexdigest(),
            hashlib.sha256(certificate_header.encode("ascii")).hexdigest(),
        )
    ).encode("utf-8")


SignerRefresh = Callable[[], tuple[Ed25519PrivateKey, str, int]]


@dataclass(slots=True)
class ResidentRequestSigner:
    """One short-lived runtime key and its resident identity certificate."""

    runtime_private_key: Ed25519PrivateKey
    certificate_header: str
    certificate_expires_at: int = 0
    refresh: SignerRefresh | None = None

    def __post_init__(self) -> None:
        certificate = str(self.certificate_header or "").strip()
        if not _BASE64URL_RE.fullmatch(certificate) or len(certificate) > 16_384:
            raise ResidentSigningError(
                "Resident runtime certificate header is invalid."
            )
        self.certificate_header = certificate

    def _refresh_if_needed(self, *, now: int) -> None:
        if (
            self.refresh is None
            or self.certificate_expires_at <= 0
            or now < self.certificate_expires_at - 300
        ):
            return
        runtime_key, certificate, expires_at = self.refresh()
        if not _BASE64URL_RE.fullmatch(certificate) or len(certificate) > 16_384:
            raise ResidentSigningError("Refreshed resident certificate is invalid.")
        self.runtime_private_key = runtime_key
        self.certificate_header = certificate
        self.certificate_expires_at = int(expires_at)

    def signed_headers(
        self,
        *,
        method: str,
        target: str,
        body: bytes = b"",
        timestamp: int | None = None,
        nonce: str | None = None,
    ) -> dict[str, str]:
        """Sign the exact method, encoded path/query, and serialized body."""

        request_method = str(method or "").strip().upper()
        request_target = str(target or "").strip()
        request_body = bytes(body)
        now = int(time.time()) if timestamp is None else int(timestamp)
        self._refresh_if_needed(now=now)
        signed_at = str(now)
        request_nonce = str(nonce or secrets.token_urlsafe(18)).strip()
        if not _METHOD_RE.fullmatch(request_method):
            raise ResidentSigningError("Resident request method is invalid.")
        if (
            not request_target.startswith("/")
            or "\n" in request_target
            or "\r" in request_target
        ):
            raise ResidentSigningError("Resident request target is invalid.")
        try:
            request_target.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ResidentSigningError(
                "Resident request target must use its encoded HTTP form."
            ) from exc
        if not _NONCE_RE.fullmatch(request_nonce):
            raise ResidentSigningError("Resident request nonce is invalid.")
        signature = self.runtime_private_key.sign(
            _canonical_request(
                method=request_method,
                target=request_target,
                body=request_body,
                timestamp=signed_at,
                nonce=request_nonce,
                certificate_header=self.certificate_header,
            )
        )
        return {
            RESIDENT_CERTIFICATE_HEADER: self.certificate_header,
            RESIDENT_TIMESTAMP_HEADER: signed_at,
            RESIDENT_NONCE_HEADER: request_nonce,
            RESIDENT_SIGNATURE_HEADER: _encode(signature),
        }


def signer_from_host_sealed_identity(
    resident_dir: Path,
    *,
    audience: str,
    host_transport_private_key_path: str | Path | None = None,
    lifetime_seconds: int = DEFAULT_CERTIFICATE_LIFETIME_SECONDS,
) -> ResidentRequestSigner:
    """Build a renewable signer for one active hearth generation."""

    home = Path(resident_dir)
    descriptor = load_resident_identity_descriptor(home)
    manifest = load_hearth_manifest(home)
    configured_key_path = str(
        host_transport_private_key_path
        or str(os.environ.get("WW_HEARTH_TRANSPORT_PRIVATE_KEY") or "").strip()
    ).strip()
    if not configured_key_path:
        raise ResidentSigningError("The hearth host transport key is not configured.")
    key_path = Path(configured_key_path).expanduser()
    expected_generation = manifest.runtime_generation

    def refresh() -> tuple[Ed25519PrivateKey, str, int]:
        current = load_hearth_manifest(home)
        if current.runtime_generation != expected_generation:
            raise ResidentSigningError(
                "Resident hearth generation changed while this runtime was active."
            )
        host_private_key = load_transport_private_key(key_path)
        identity_private_key = open_sealed_resident_identity_private_key(
            load_resident_key_seal(
                home / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME
            ),
            identity_descriptor=descriptor,
            recipient_transport_private_key=host_private_key,
        )
        runtime_private_key = Ed25519PrivateKey.generate()
        certificate, expires_at = issue_runtime_certificate_header(
            identity_private_key=identity_private_key,
            runtime_public_key=runtime_private_key.public_key(),
            actor_id=descriptor.actor_id,
            hearth_shard_id=descriptor.hearth_shard_id,
            runtime_generation=current.runtime_generation,
            audience=audience,
            lifetime_seconds=lifetime_seconds,
        )
        return runtime_private_key, certificate, expires_at

    runtime_key, certificate, expires_at = refresh()
    return ResidentRequestSigner(
        runtime_private_key=runtime_key,
        certificate_header=certificate,
        certificate_expires_at=expires_at,
        refresh=refresh,
    )
