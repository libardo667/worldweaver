# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared HTTP actor proof for human and resident city sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..models import Player, SessionVars
from .auth_service import get_current_player_strict
from .federation_identity import current_shard_id
from .resident_authority import (
    ResidentAuthorityError,
    authorize_resident_request,
)
from .resident_protocol import (
    RESIDENT_CERTIFICATE_HEADER,
    RESIDENT_NONCE_HEADER,
    RESIDENT_SIGNATURE_HEADER,
    RESIDENT_TIMESTAMP_HEADER,
)

_RESIDENT_HEADERS = (
    RESIDENT_CERTIFICATE_HEADER,
    RESIDENT_TIMESTAMP_HEADER,
    RESIDENT_NONCE_HEADER,
    RESIDENT_SIGNATURE_HEADER,
)


class ActorAuthorizationError(ValueError):
    """The supplied proof cannot act through the requested city session."""

    def __init__(self, code: str, message: str, *, status_code: int):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class RequestActorCredentials:
    """Proof material gathered from one exact HTTP request."""

    player: Player | None
    method: str
    target: str
    body: bytes
    resident_headers: Mapping[str, str]

    @property
    def has_resident_proof(self) -> bool:
        return any(
            str(self.resident_headers.get(name) or "").strip()
            for name in _RESIDENT_HEADERS
        )


@dataclass(frozen=True, slots=True)
class AuthorizedActor:
    """Small proven identity record passed into ordinary domain rules."""

    actor_id: str
    session_id: str
    proof_kind: str
    player_id: str | None = None
    runtime_generation: int | None = None


async def get_request_actor_credentials(
    request: Request,
    player: Player | None = Depends(get_current_player_strict),
) -> RequestActorCredentials:
    """Gather human or resident proof without yet claiming a session."""

    resident_headers = {
        name: str(request.headers.get(name) or "") for name in _RESIDENT_HEADERS
    }
    has_resident_proof = any(value.strip() for value in resident_headers.values())
    if player is not None and has_resident_proof:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ambiguous_actor_proof",
                "message": "Use either human login or resident request proof, not both.",
            },
        )
    raw_path = request.scope.get("raw_path")
    raw_query = request.scope.get("query_string")
    if not isinstance(raw_path, bytes):
        raw_path = request.url.path.encode("ascii")
    if not isinstance(raw_query, bytes):
        raw_query = str(request.url.query or "").encode("ascii")
    try:
        target = raw_path.decode("ascii")
        if raw_query:
            target = f"{target}?{raw_query.decode('ascii')}"
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_request_target",
                "message": "Request path and query must use encoded HTTP bytes.",
            },
        ) from exc
    return RequestActorCredentials(
        player=player,
        method=request.method,
        target=target,
        body=await request.body(),
        resident_headers=resident_headers,
    )


def authorize_session_actor(
    db: Session,
    *,
    credentials: RequestActorCredentials,
    session_id: str,
    required_scope: str,
    expected_audience: str | None = None,
) -> AuthorizedActor:
    """Resolve one human JWT or resident signature to the session's actor."""

    normalized_session_id = str(session_id or "").strip()
    session_row = (
        db.get(SessionVars, normalized_session_id) if normalized_session_id else None
    )

    if credentials.player is not None:
        player = credentials.player
        player_actor_id = str(player.actor_id or player.id or "").strip()
        if (
            session_row is None
            or session_row.player_id != player.id
            or str(session_row.actor_id or "").strip() != player_actor_id
        ):
            raise ActorAuthorizationError(
                "session_actor_mismatch",
                "The logged-in actor does not control this session.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return AuthorizedActor(
            actor_id=player_actor_id,
            session_id=normalized_session_id,
            proof_kind="human_jwt",
            player_id=str(player.id),
        )

    if credentials.has_resident_proof:
        try:
            verified = authorize_resident_request(
                db,
                session_id=normalized_session_id,
                expected_audience=expected_audience or current_shard_id(),
                required_scope=required_scope,
                method=credentials.method,
                target=credentials.target,
                body=credentials.body,
                headers=credentials.resident_headers,
            )
        except ResidentAuthorityError as exc:
            error_status = (
                status.HTTP_409_CONFLICT
                if exc.code in {"replayed_request", "retired_generation"}
                else status.HTTP_401_UNAUTHORIZED
            )
            raise ActorAuthorizationError(
                exc.code,
                str(exc),
                status_code=error_status,
            ) from exc
        return AuthorizedActor(
            actor_id=verified.actor_id,
            session_id=normalized_session_id,
            proof_kind="resident_signature",
            runtime_generation=verified.runtime_generation,
        )

    raise ActorAuthorizationError(
        "actor_proof_required",
        "This session command requires human login or resident request proof.",
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


def actor_authorization_http_error(exc: ActorAuthorizationError) -> HTTPException:
    """Translate the shared service error at the API boundary."""

    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    )
