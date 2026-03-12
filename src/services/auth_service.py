"""Auth service — password hashing, JWT, FastAPI dependencies."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Player

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(player_id: str) -> str:
    from datetime import timedelta
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": player_id, "exp": expire},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> Optional[str]:
    """Return player_id or None on any failure."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_current_player(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[Player]:
    """Dependency: returns Player or None (anonymous/Observer)."""
    if not credentials:
        return None
    player_id = decode_token(credentials.credentials)
    if not player_id:
        return None
    return db.get(Player, player_id)


def require_player(
    player: Optional[Player] = Depends(get_current_player),
) -> Player:
    """Dependency: raises 401 if not authenticated."""
    if not player:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return player


def check_pass_not_expired(player: Player) -> None:
    """Raise 403 if the player's visitor pass has expired. Safe to call directly."""
    if player.pass_expires_at is not None:
        expires = player.pass_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "pass_expired"},
            )


def require_active_pass(
    player: Player = Depends(require_player),
) -> Player:
    """Dependency version of pass check — use with Depends() in route signatures."""
    check_pass_not_expired(player)
    return player
