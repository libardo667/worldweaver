# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sign exact city requests for one already-authorized resident runtime.

This module does not create resident identities, issue certificates, or read key
files. A host may inject one short-lived runtime private key and its identity-
signed certificate after a reviewed admission procedure.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import re
import secrets
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

RESIDENT_CERTIFICATE_HEADER = "X-WW-Resident-Certificate"
RESIDENT_TIMESTAMP_HEADER = "X-WW-Resident-Timestamp"
RESIDENT_NONCE_HEADER = "X-WW-Resident-Nonce"
RESIDENT_SIGNATURE_HEADER = "X-WW-Resident-Signature"

_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_METHOD_RE = re.compile(r"^[A-Z]{1,16}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class ResidentSigningError(ValueError):
    """A runtime signer or exact request cannot be represented safely."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


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


@dataclass(frozen=True, slots=True)
class ResidentRequestSigner:
    """One short-lived runtime key and its resident identity certificate."""

    runtime_private_key: Ed25519PrivateKey
    certificate_header: str

    def __post_init__(self) -> None:
        certificate = str(self.certificate_header or "").strip()
        if not _BASE64URL_RE.fullmatch(certificate) or len(certificate) > 16_384:
            raise ResidentSigningError(
                "Resident runtime certificate header is invalid."
            )
        object.__setattr__(self, "certificate_header", certificate)

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
        signed_at = str(int(time.time()) if timestamp is None else int(timestamp))
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
