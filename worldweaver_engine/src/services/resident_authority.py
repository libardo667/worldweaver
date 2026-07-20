# SPDX-License-Identifier: AGPL-3.0-or-later
"""City-side storage and verification for resident runtime authority.

Private resident keys never belong here. The city stores an admitted public
identity key, the generation attached to a local session, and short-lived
replay records for already accepted signed requests.
"""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Mapping

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    ResidentAuthority,
    ResidentRequestNonce,
    ResidentSessionAuthority,
    SessionVars,
)
from .resident_protocol import (
    DEFAULT_MAX_CLOCK_SKEW_SECONDS,
    RESIDENT_CERTIFICATE_HEADER,
    ResidentProtocolError,
    ResidentRuntimeCertificate,
    VerifiedResidentRequest,
    identity_key_id,
    verify_resident_request,
    verify_runtime_certificate,
)


class ResidentAuthorityError(ValueError):
    """A city cannot admit or authorize this resident runtime."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _bounded_identifier(value: str, *, label: str, max_length: int) -> str:
    cleaned = str(value or "").strip()
    if not cleaned or len(cleaned) > max_length:
        raise ResidentAuthorityError("invalid_binding", f"Resident {label} is invalid.")
    return cleaned


def bind_resident_identity(
    db: Session,
    *,
    actor_id: str,
    hearth_shard_id: str,
    identity_public_key: str,
    recovery_policy_version: int = 1,
) -> ResidentAuthority:
    """Record an explicitly admitted resident public key.

    This function intentionally has no public HTTP route. The caller must be a
    reviewed creation, migration, or recovery procedure rather than anonymous
    first-use traffic.
    """

    actor = _bounded_identifier(actor_id, label="actor ID", max_length=36)
    hearth = _bounded_identifier(hearth_shard_id, label="hearth shard ID", max_length=80)
    public_key = _bounded_identifier(identity_public_key, label="identity public key", max_length=64)
    try:
        key_id = identity_key_id(public_key)
    except ResidentProtocolError as exc:
        raise ResidentAuthorityError("invalid_binding", str(exc)) from exc
    if isinstance(recovery_policy_version, bool) or not isinstance(recovery_policy_version, int) or recovery_policy_version < 1:
        raise ResidentAuthorityError("invalid_binding", "Resident recovery policy version is invalid.")

    existing = db.get(ResidentAuthority, actor)
    if existing is not None:
        if existing.hearth_shard_id != hearth or existing.identity_public_key != public_key or existing.identity_key_id != key_id:
            raise ResidentAuthorityError(
                "identity_conflict",
                "Resident identity is already bound to different public continuity.",
            )
        return existing

    key_owner = db.query(ResidentAuthority).filter(ResidentAuthority.identity_key_id == key_id).one_or_none()
    if key_owner is not None:
        raise ResidentAuthorityError(
            "identity_conflict",
            "Resident identity key is already bound to another actor.",
        )

    authority = ResidentAuthority(
        actor_id=actor,
        hearth_shard_id=hearth,
        identity_public_key=public_key,
        identity_key_id=key_id,
        recovery_policy_version=recovery_policy_version,
    )
    db.add(authority)
    db.flush()
    return authority


def activate_resident_generation(
    db: Session,
    *,
    certificate: ResidentRuntimeCertificate,
    expected_audience: str,
    required_scope: str = "session.bootstrap",
    now: int | None = None,
) -> ResidentAuthority:
    """Accept the same or a newer identity-signed runtime generation."""

    authority = db.get(ResidentAuthority, certificate.actor_id)
    if authority is None:
        raise ResidentAuthorityError("identity_not_admitted", "Resident identity is not admitted by this city.")
    if authority.hearth_shard_id != certificate.hearth_shard_id:
        raise ResidentAuthorityError("identity_conflict", "Resident certificate names a different hearth.")
    try:
        verify_runtime_certificate(
            certificate,
            identity_public_key=str(authority.identity_public_key),
            expected_actor_id=str(authority.actor_id),
            expected_runtime_generation=int(certificate.runtime_generation),
            expected_audience=expected_audience,
            required_scope=required_scope,
            now=now,
        )
    except ResidentProtocolError as exc:
        raise ResidentAuthorityError("invalid_proof", str(exc)) from exc

    active = authority.active_runtime_generation
    if active is not None and certificate.runtime_generation < int(active):
        raise ResidentAuthorityError(
            "retired_generation",
            "Resident runtime generation has already been retired.",
        )
    if active is None or certificate.runtime_generation > int(active):
        authority.active_runtime_generation = certificate.runtime_generation
        db.flush()
    return authority


def bind_resident_session(
    db: Session,
    *,
    session_id: str,
    actor_id: str,
    runtime_generation: int,
) -> ResidentSessionAuthority:
    """Attach one admitted active generation to an existing resident session."""

    session_key = _bounded_identifier(session_id, label="session ID", max_length=64)
    actor = _bounded_identifier(actor_id, label="actor ID", max_length=36)
    if isinstance(runtime_generation, bool) or not isinstance(runtime_generation, int) or runtime_generation < 1:
        raise ResidentAuthorityError(
            "generation_mismatch",
            "Resident session generation is not active.",
        )
    session_row = db.get(SessionVars, session_key)
    if session_row is None or session_row.actor_id != actor or session_row.player_id is not None:
        raise ResidentAuthorityError(
            "session_mismatch",
            "Resident session does not belong to the admitted actor.",
        )
    authority = db.get(ResidentAuthority, actor)
    if authority is None or authority.active_runtime_generation != runtime_generation:
        raise ResidentAuthorityError(
            "generation_mismatch",
            "Resident session generation is not active.",
        )

    binding = db.get(ResidentSessionAuthority, session_key)
    if binding is None:
        binding = ResidentSessionAuthority(
            session_id=session_key,
            actor_id=actor,
            runtime_generation=runtime_generation,
        )
        db.add(binding)
    elif binding.actor_id != actor:
        raise ResidentAuthorityError(
            "session_mismatch",
            "Resident session is already bound to another actor.",
        )
    else:
        binding.runtime_generation = runtime_generation
    db.flush()
    return binding


def _consume_request_nonce(
    db: Session,
    *,
    verified: VerifiedResidentRequest,
    now: int,
    max_clock_skew_seconds: int,
) -> None:
    """Commit one verified nonce and any authority change made before it."""

    cutoff = datetime.fromtimestamp(
        now - (max_clock_skew_seconds * 2),
        tz=timezone.utc,
    )
    db.query(ResidentRequestNonce).filter(ResidentRequestNonce.received_at < cutoff).delete(synchronize_session=False)
    db.add(
        ResidentRequestNonce(
            certificate_id=verified.certificate_id,
            nonce=verified.nonce,
            actor_id=verified.actor_id,
            runtime_generation=verified.runtime_generation,
            signed_at=datetime.fromtimestamp(verified.signed_at, tz=timezone.utc),
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResidentAuthorityError(
            "replayed_request",
            "Signed resident request was already used.",
        ) from exc


def authorize_resident_bootstrap_request(
    db: Session,
    *,
    actor_id: str,
    expected_audience: str,
    method: str,
    target: str,
    body: bytes,
    headers: Mapping[str, str],
    now: int | None = None,
    max_clock_skew_seconds: int = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
) -> VerifiedResidentRequest:
    """Verify the first signed request before the resident has a city session.

    The stable public identity must already have been admitted by a separate,
    reviewed procedure. A valid request may activate the same or a newer
    short-lived runtime generation. It cannot create an identity binding.
    """

    actor = _bounded_identifier(actor_id, label="actor ID", max_length=36)
    if db.new or db.dirty or db.deleted:
        raise ResidentAuthorityError(
            "authorization_session_dirty",
            "Resident authorization must run before other database changes.",
        )
    certificate_header = str(headers.get(RESIDENT_CERTIFICATE_HEADER) or "").strip()
    try:
        certificate = ResidentRuntimeCertificate.decode_header(certificate_header)
    except ResidentProtocolError as exc:
        raise ResidentAuthorityError("invalid_proof", str(exc)) from exc
    if certificate.actor_id != actor:
        raise ResidentAuthorityError(
            "actor_mismatch",
            "Resident bootstrap proof belongs to another actor.",
        )

    authority = db.get(ResidentAuthority, actor)
    if authority is None:
        raise ResidentAuthorityError(
            "identity_not_admitted",
            "Resident identity is not admitted by this city.",
        )
    if authority.hearth_shard_id != certificate.hearth_shard_id:
        raise ResidentAuthorityError(
            "identity_conflict",
            "Resident certificate names a different hearth.",
        )
    active = authority.active_runtime_generation
    if active is not None and certificate.runtime_generation < int(active):
        raise ResidentAuthorityError(
            "retired_generation",
            "Resident runtime generation has already been retired.",
        )

    try:
        verified = verify_resident_request(
            identity_public_key=str(authority.identity_public_key),
            expected_actor_id=actor,
            expected_runtime_generation=int(certificate.runtime_generation),
            expected_audience=expected_audience,
            required_scope="session.bootstrap",
            method=method,
            target=target,
            body=body,
            headers=headers,
            now=now,
            max_clock_skew_seconds=max_clock_skew_seconds,
        )
    except ResidentProtocolError as exc:
        raise ResidentAuthorityError("invalid_proof", str(exc)) from exc

    if active is None or certificate.runtime_generation > int(active):
        authority.active_runtime_generation = certificate.runtime_generation
    current_time = int(time.time()) if now is None else int(now)
    _consume_request_nonce(
        db,
        verified=verified,
        now=current_time,
        max_clock_skew_seconds=max_clock_skew_seconds,
    )
    return verified


def authorize_resident_request(
    db: Session,
    *,
    session_id: str,
    expected_audience: str,
    required_scope: str,
    method: str,
    target: str,
    body: bytes,
    headers: Mapping[str, str],
    now: int | None = None,
    max_clock_skew_seconds: int = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
) -> VerifiedResidentRequest:
    """Verify one current session request and permanently consume its nonce.

    The nonce commit happens before domain work so a rejected world command
    cannot accidentally make the exact signed request reusable. Call this from
    a clean request dependency, before adding or changing other database rows.
    """

    session_key = _bounded_identifier(session_id, label="session ID", max_length=64)
    if db.new or db.dirty or db.deleted:
        raise ResidentAuthorityError(
            "authorization_session_dirty",
            "Resident authorization must run before other database changes.",
        )
    session_row = db.get(SessionVars, session_key)
    binding = db.get(ResidentSessionAuthority, session_key)
    if session_row is None or binding is None or session_row.actor_id != binding.actor_id:
        raise ResidentAuthorityError("session_not_authorized", "Resident session has no authority binding.")
    authority = db.get(ResidentAuthority, binding.actor_id)
    if authority is None or authority.active_runtime_generation != binding.runtime_generation:
        raise ResidentAuthorityError("retired_generation", "Resident session generation is no longer active.")

    try:
        verified = verify_resident_request(
            identity_public_key=str(authority.identity_public_key),
            expected_actor_id=str(binding.actor_id),
            expected_runtime_generation=int(binding.runtime_generation),
            expected_audience=expected_audience,
            required_scope=required_scope,
            method=method,
            target=target,
            body=body,
            headers=headers,
            now=now,
            max_clock_skew_seconds=max_clock_skew_seconds,
        )
    except ResidentProtocolError as exc:
        raise ResidentAuthorityError("invalid_proof", str(exc)) from exc

    current_time = int(time.time()) if now is None else int(now)
    _consume_request_nonce(
        db,
        verified=verified,
        now=current_time,
        max_clock_skew_seconds=max_clock_skew_seconds,
    )
    return verified
