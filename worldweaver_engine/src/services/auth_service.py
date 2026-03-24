"""Auth service - password hashing, JWT helpers, and FastAPI dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Player

ALGORITHM = "HS256"

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class DecodedTokenSubject:
    subject: str
    token_type: str


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(actor_id: str) -> str:
    from datetime import timedelta

    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": actor_id, "exp": expire, "token_type": "actor"},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def decode_token_subject(token: str) -> Optional[DecodedTokenSubject]:
    """Return actor metadata for new tokens or legacy player metadata for old ones."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        return None
    subject = str(payload.get("sub") or "").strip()
    if not subject:
        return None
    token_type = str(payload.get("token_type") or "legacy_player").strip() or "legacy_player"
    return DecodedTokenSubject(subject=subject, token_type=token_type)


def _auth_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": code, "message": message},
    )


def _resolve_current_player(
    credentials: Optional[HTTPAuthorizationCredentials],
    db: Session,
    *,
    strict: bool,
) -> Optional[Player]:
    if not credentials:
        return None

    decoded = decode_token_subject(credentials.credentials)
    if not decoded:
        if strict:
            raise _auth_error(
                "invalid_auth_token",
                "The saved login on this shard could not be read. Sign in again here.",
            )
        return None

    if decoded.token_type == "actor":
        player = db.query(Player).filter(Player.actor_id == decoded.subject).first()
        if player is not None:
            return player

        from .federation_identity import sync_player_projection_from_actor_id

        player = sync_player_projection_from_actor_id(db, decoded.subject)
        if player is not None:
            return player
        if strict:
            raise _auth_error(
                "actor_projection_unavailable",
                "This shard could not recover your local account projection. Sign in again on this shard.",
            )
        return None

    if strict:
        raise _auth_error(
            "legacy_auth_token",
            "This saved login predates shard-wide actor identity. Sign in again on this shard.",
        )
    return db.get(Player, decoded.subject)


def get_current_player(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[Player]:
    """Dependency: returns a local player projection or None for anonymous users."""
    return _resolve_current_player(credentials, db, strict=False)


def get_current_player_strict(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[Player]:
    """Return None for anonymous users, but reject invalid or stale auth explicitly."""
    return _resolve_current_player(credentials, db, strict=True)


def require_player(
    player: Optional[Player] = Depends(get_current_player_strict),
) -> Player:
    """Dependency: raises 401 if not authenticated."""
    if not player:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return player


def check_pass_not_expired(player: Player) -> None:
    """Legacy compatibility shim: account age no longer forces observer-only access."""
    return None


def require_active_pass(
    player: Player = Depends(require_player),
) -> Player:
    """Legacy compatibility dependency that now simply returns the authenticated player."""
    check_pass_not_expired(player)
    return player
